from django.db.models import Q
from django.db.models import F
from django.utils import timezone

import celery_tasks
from celery import result
import datetime
from image.models import ImageProfile
from image import image_profile
import group
from models import *
import pytz
import string
from utils.exception import IgniteException
from utils.utils import parse_file
import logging
logger = logging.getLogger(__name__)


def get_all_job():
    return Job.objects.all()


def ref_count_delete(job):
    for grp in job.tasks:
        value = -1
        Group.objects.filter(pk=grp["group_id"]).update(ref_count=F('ref_count')+value)


def ref_count_add(grp):
    value = 1
    Group.objects.filter(pk=grp.id).update(ref_count=F('ref_count')+value)


def tasks_validation(data, options, job):
    from celery_tasks import get_all_switches
    tsk = []
    if len(data) == 0:
        raise IgniteException("Job cannot have empty task sequence")
    if options == "update":
        ref_count_delete(job)
    for task in data:
        try:
            grp = group.get_group(task["group_id"])
            img = image_profile.get_profile(task["image_id"])
            if options!= 'get' and img.system_image == None:
                raise IgniteException("No system image is found in the image profile: "+ img.profile_name)
            if options!= 'get' and task['type'] == 'epld_upgrade' and img.epld_image == None:
                raise IgniteException("No epld image is found in the image profile: "+ img.profile_name)
            if options!='get' and img.access_protocol != 'scp':
                raise IgniteException("Only scp protocol is supported for image profile: "+ img.profile_name)
            task["switch_count"] = len(grp.switch_list)
            switches = get_all_switches(task)
            task['group']['switches'] = switches
            task['params']={} 
            task['params']['image'] = {}
            image = {}
            image['profile_name'] = img.profile_name
            image['system_image'] = img.system_image
            image['id'] = img.id
            image['image_server_ip'] = img.image_server_ip
            image['image_server_username'] = img.image_server_username
            image['image_server_password'] = img.image_server_password
            image['access_protocol'] = img.access_protocol
            if task['type'] == 'epld_upgrade':
                image['epld_image'] = img.epld_image
            task['params']['image'] = image
            task["image_name"] = img.profile_name
            tsk.append(task)
            if options != "get":
                ref_count_add(grp)
        except Group.DoesNotExist as e:
            raise IgniteException("Group id "+str(task["group_id"])+" not found")
        except ImageProfile.DoesNotExist as e:
            raise IgniteException("Image id "+str(task["image_id"])+" not found")
    return tsk


def add_job(data, user):
    tsk = tasks_validation(data["tasks"], "add", 0)
    jb = Job()
    jb.name = data["name"]
    date_time = datetime.datetime.strptime(data["schedule"], "%Y-%m-%dT%H:%M:%S")
    cur_time = datetime.datetime.utcnow()
    if cur_time >= date_time:
        raise IgniteException("schedule time has elapsed")
#   set timezone information
    date_time = timezone.make_aware(date_time, pytz.timezone('UTC'))
    jb.schedule = date_time
    jb.tasks = data["tasks"]
    jb.updated_by = user
    jb.save()
#   create celery task
    jb.task_id = celery_tasks.run_single_job.apply_async([jb.id, jb.schedule], eta=jb.schedule)
    jb.save()
    jb.tasks = tsk
    return jb


def get_job(id):
    jb = Job.objects.get(pk=id)
    if jb.status in ['SCHEDULED', 'RUNNING']:
        tsk = tasks_validation(jb.tasks, "get", 0)
        jb.tasks = tsk
    return jb


def assert_django_job(status, option):
    if not status == 'SCHEDULED':
        if status == 'RUNNING':
            raise IgniteException("Job is running")
        elif option == "update":
            raise IgniteException("Job is completed")


def update_job(id, data, user):
    jb = Job.objects.get(pk=id)
    assert_django_job(jb.status, "update")
    tsk = tasks_validation(data["tasks"], "update", jb)
    jb.name = data["name"]
    date_time = datetime.datetime.strptime(data["schedule"], "%Y-%m-%dT%H:%M:%S")
    cur_time = datetime.datetime.utcnow()
    if cur_time >= date_time:
        raise IgniteException("Schedule time has elapsed")
#   set timezone information
    date_time = timezone.make_aware(date_time, pytz.timezone('UTC'))
    res = result.AsyncResult(jb.task_id)
    res.revoke()
    jb.schedule = date_time
    jb.tasks = data["tasks"]
    jb.updated_by = user
    jb.task_id = celery_tasks.run_single_job.apply_async([jb.id, jb.schedule], eta=jb.schedule).task_id
    jb.save()
    jb.tasks = tsk
    return jb


def delete_job(id):
    jb = Job.objects.get(pk=id)
    assert_django_job(jb.status, "delete")
    if jb.status == "SCHEDULED":
        res = result.AsyncResult(jb.task_id)
        res.revoke()
        ref_count_delete(jb)
    jb.delete()