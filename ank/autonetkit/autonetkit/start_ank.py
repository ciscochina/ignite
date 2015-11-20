'''
This file has a function run_ank which acts as a bridge
between the poap and ank tool. It takes 4 arguments:
topo_file--This is the input topology jason file generated by poap.
cfg_file--It contains device profiles which in turn are a collection of configs to be applied on the device.
loc------This is the location where config files generated by poap are placed.
fab------This is the fabric name containg replica number also.

run_ank takes above 4 parameters as input and passes the 1st 2 arguments to ank.
ank in turn generates the output configuration files and returns the folder name.
At the end, files generated by ank are concatenated with the configuration files
generated by poap.
'''
from autonetkit import json_converter
import autonetkit.log as log

def run_ank(topo_file, cfg_file, fab='', loc='',  syntax ='nx_os'):
    try:
        #dst_folder is the place where ank places it's output config files
        #print loc
        #print fab
        if fab is None or loc is None or topo_file is None or cfg_file is None:
            log.error("start_ank.py...one or more parameters to run_ank is empty")
            return None
        dst_folder = json_converter.main(topo_file, cfg_file, syntax)
        #print dst_folder
        line_ank = "!!!!!!!!!!!!!!!!!!!!!!!!!!!ANK CONFIG!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        line_poap = "!!!!!!!!!!!!!!!!!!!!!!!!!!!POAP CONFIG!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        if dst_folder is not None:
            import os
            import re
            #fn_ank is the name of the file generated by ank
            #fn_poap is the name of the file generated by poap
            for fn_ank in os.listdir(dst_folder):
                '''
                while generating output files ank replaces '-' in output file
                name with '_'. Therefore we are taking out both to make it easier
                for string matching.
                '''
                fn_ank_temp = re.sub('[-_]', '', fn_ank[:len(fn_ank)-5])#ignore .conf at the end
                #print fn_ank_temp
                #for fn_poap in os.listdir('/home/dev/ignite/repo'):
                for fn_poap in os.listdir(loc):
                    #print fn_poap
                    #print fn_poap[:len(fab)]
                    #print fab
                    if fn_poap[:len(fab)] == fab:
                        pod_re = "([_])(.+)"
                        id = (re.search(pod_re,fn_poap[len(fab):])).group(2)#this will give the device name
                        id = re.sub('[-_]','',id[:len(id)-4])#ignore .cfg at end
                        #print id
                        if  id == fn_ank_temp:
                            file = loc + fn_poap
                            #print file
                            with open(file, "r") as fpc:
                                buff_poap = fpc.read()
                            file_ank = dst_folder + '/' + fn_ank
                            with open(file_ank,"r") as f_ank:
                                buff_ank = f_ank.read()
                            with open(file, "w+") as fpc:
                                fpc.write(line_ank)
                                fpc.write(buff_ank)
                                fpc.write(line_poap)
                                fpc.write(buff_poap)


            return 1

        else:
            log.error("start_ank.py...ank returned destination folder as None")
            return None

    except:
        log.error("start_ank.py...exception recieved in call to json_converter")
        return None
