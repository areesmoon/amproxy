#!/usr/bin/python3
import sys
import subprocess
import json
import os
import sqlite3
import math
import yaml
import re
import signal


# NOTE:
# if error running executable binary, run to fix:
# sudo mount /tmp -o remount,exec

def signal_handler(sig, frame):
    sys.exit(0)

def db_escape_field(field):
    return field.replace("'", "''")

def db_execute(query):
    if check_arg("-d"): print("Running query: " + query)
    conn = sqlite3.connect(file_db)
    cursor = conn.execute(query)
    rows = []
    for row in cursor:
        rows.append(row)
    conn.commit()
    conn.close()
    return rows
    
def db_select(table, by, field):
    query = "select * from " + table + " where " + by + " = '" + str(field) + "'"
    if check_arg("-d"): print("Running query: " + query)
    rows = db_execute(query)
    if len(rows)>0:
        return rows[0]
    else:
        return rows

def replace_variable(text):
    for key in obj_replace:
        text = text.replace("${" + key + "}", obj_replace[key])
    return text

def get_indent(num):
    return " " * num * 4

def check_arg(arg):
    global args
    for i in args:
        if i==arg:
            return True
    return False

def get_arg(index):
    global args
    if len(args) >= index + 1: return args[index]
    else: return ""

def get_arg_after(after):
    global args
    for i in range(0, len(args)-1):
        if args[i]==after:
            return args[i+1]

def get_app():
    return get_arg_after("-n")

def get_app_prefix(app):
    return app + '-'

def checkArg(index):
    return index <= len(sys.argv)

def list2json(list):
    str_resp = ''.join(map(str, list))
    return json.loads(str_resp)

def split_command_args(command):
    return command.split(" ")

def run_command(command, attach = False):
    if check_arg("-d"): print("Running command: {}".format(command))
    if attach:
        params = command.split(" ")
        subprocess.call(params)
    else:
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        list_resp = p.stdout.readlines()
        new_list_resp = []
        for line in list_resp:
            new_list_resp.append(line.rstrip())
        return new_list_resp

def run_docker_command(command, attach = False):
    return run_command("docker " + command, attach)

def print_json(obj):
    print(json.dumps(obj, indent=4))
    
def clean_yaml(text):
    ar_new = text.split("\n")
    new_text = ""
    for line in ar_new:
        if line != "":
            if line[0] != "#":
                new_text = new_text + "\n" + line
    return new_text

def docker_compose(file, option="", attach=False):
    command = "compose -f " + file + " up" + (" " + option if option != "" else "")
    run_docker_command(command, attach)
    
def network_create(app):
    resp = run_docker_command("network create --driver=bridge " + get_app_prefix(app) + 'net')
    if resp==[]:
        print("Network " + get_app_prefix(app) + 'net' + " already existed")
    else:
        print("Network " + get_app_prefix(app) + 'net' + " is created")
    
def network_get(app):
    global args
    resp = run_docker_command("network inspect " + get_app_prefix(app) + 'net')
    print_json(list2json(resp))
    
def network_delete(app):
    resp = run_docker_command("network rm " + get_app_prefix(app) + 'net')
    if(resp==[]):
        print("Network not found")
    elif(resp[0]==get_app_prefix(app) + 'net'):
        print("Network " + get_app_prefix(app) + 'net' + " is deleted")
        
def update_obj_replace(app_id):
    row_app = db_select("tb_app", "id", app_id)
    app = row_app[1]
    ports = row_app[2]
    
    #app name
    obj_replace["app"] = app
    
    # ports
    ports = ports
    ar_port = ports.split(":")
    obj_replace["external_port"] = ar_port[0]
    obj_replace["container_port"] = ar_port[1]
    obj_replace["statistic_port"] = ar_port[2]
    
def get_iterable_container_tpl(tpl_dc):
    # user's docker-compose
    dc = replace_variable(tpl_dc)
    
    # get iterable container
    ar_dc = dc.split("### ITERABLE CONTAINER BLOCK ###")
    return ar_dc[1]
    
def get_non_iterable_container_tpl(tpl_dc):
    # user's docker-compose
    dc = replace_variable(tpl_dc)
    
    # get iterable container
    ar_dc = dc.split("### ITERABLE CONTAINER BLOCK ###")
    
    # get non iterable container 
    ar_dc1 = ar_dc[0].split("### NON ITERABLE CONTAINER BLOCK ###")
    return ar_dc1[1] if len(ar_dc1)==2 else ""

def delete_n_first_container(app_id, n):
    row_app = db_select("tb_app", "id", app_id)
    app = row_app[1]
    rows = db_execute("SELECT id, no from tb_ctn where app_id = '" + str(app_id) + "' LIMIT 0," + str(n))
    for row in rows:
        print("Deleting app resource " + app + '-' + str(row[1]))
        resp = stop_delete_container(app + "-" + str(row[1]))
        if resp != "":
            db_execute("DELETE FROM tb_ctn WHERE id = '" + str(row[0]) + "'")
        else:
            print("Failed!")

def update_haproxy_cfg(app_id):
    update_obj_replace(app_id)
    cfg = clean_yaml(tpl_cfg)
    rows = db_execute("SELECT no from tb_ctn where app_id = '" + str(app_id) + "'")
    if len(rows) > 0:
        for row in rows:
            cfg = cfg + "\n    " + tpl_backend_server.replace("${no}", str(row[0]))
    cfg = replace_variable(cfg)
    f = open(dir_cfg + "/" + "haproxy.cfg", "w")
    f.write(cfg + "\n")
    f.close()
    
def refresh_service(app_id):
    row_app = db_select("tb_app", "id", app_id)
    update_haproxy_cfg(app_id)
    run_docker_command("kill -s HUP " + row_app[1] + "-proxy")
    
def create_proxy_service(app_id, yaml_file = None):
    update_obj_replace(app_id)
    
    proxy= replace_variable(tpl_proxy)
    container_network = replace_variable(tpl_container_network)
    network = replace_variable(tpl_network)
        
    svc_proxy = "services:\n" + proxy + "\n" + container_network + "\n" + network
    yaml_file = yaml_file if yaml_file is not None else yaml_proxy
    f = open(yaml_file, "w")
    f.write(clean_yaml(svc_proxy))
    f.close()
    
def create_service_full(app_id, yaml_file=None):
    
    update_obj_replace(app_id)
    
    proxy = replace_variable(tpl_proxy)
    container_network = replace_variable(tpl_container_network)
    network = replace_variable(tpl_network)
    
    # full docker compose file
    full_dc = "services:\n" + proxy + "\n" + container_network
    
    # get non iterable
    row_app = db_select("tb_app", "id", app_id)
    tpl_dc = row_app[3]
    
    ctn_non_iterable = get_non_iterable_container_tpl(tpl_dc)
    ctn_non_iterable = clean_yaml(ctn_non_iterable)
    if(ctn_non_iterable!=''):
        full_dc = full_dc + "\n" + ctn_non_iterable + "\n" + container_network
    
    # iterable
    ctn_iterable = get_iterable_container_tpl(tpl_dc)
    ctn_iterable = clean_yaml(ctn_iterable)
    # iterate through record
    rows = db_execute("SELECT no from tb_ctn where app_id = '" + str(app_id) + "'")
    for row in rows:
        full_dc = full_dc + "\n" + ctn_iterable.replace("${no}", str(row[0])) + "\n" + container_network
        
    # close full_dc
    full_dc = full_dc + "\n" + network
    
    # write to file
    yaml_file = yaml_file if yaml_file is not None else yaml_full
    f = open(yaml_file, "w")
    f.write(clean_yaml(full_dc))
    f.close()
    
def create_service_non_iterable(app_id):
    update_obj_replace(app_id)
    
    row_app = db_select("tb_app", "id", app_id)
    tpl_dc = row_app[3]
    
    # prepare network
    container_network = replace_variable(tpl_container_network)
    network = replace_variable(tpl_network)
    
    # create service non iterable
    ctn_non_iterable = get_non_iterable_container_tpl(tpl_dc)
    ctn_non_iterable = clean_yaml(ctn_non_iterable)
    svc_non_iterable = ""
    if(ctn_non_iterable!=''):
        svc_non_iterable = "services:\n" + ctn_non_iterable + "\n" + container_network + "\n" + network
    
    # write to yaml file
    f = open(yaml_non_itr, "w")
    f.write(clean_yaml(svc_non_iterable))
    f.close()
    
def create_service_iterable(app_id, n, yaml_file = None, start_no = None, stop_no = None):
    #update variable
    update_obj_replace(app_id)
    
    row_app = db_select("tb_app", "id", app_id)
    tpl_dc = row_app[3]
    
    # prepare template
    container_network = replace_variable(tpl_container_network)
    network = replace_variable(tpl_network)
    
    # get main container image
    ctn_iterable = get_iterable_container_tpl(tpl_dc)
    
    if start_no is None:    
        start_no = db_execute("select ifnull(max(no),0)  as max_no from tb_ctn where app_id = '" + str(app_id) + "'")[0][0] + 1
        
    if stop_no is None:
        stop_no = start_no + n
    else:
        stop_no = stop_no + 1
        
    # print("Start: " + str(start_no))
    # print("Stop: " + str(stop_no))
    
    # create service iterable
    svc_iterable = "services:\n"
    for i in range(start_no, stop_no):
        svc_iterable = svc_iterable + "\n" + ctn_iterable.replace("${no}", str(i)) + "\n" + container_network
        if yaml_file is None:
            db_execute("insert into tb_ctn (app_id, no) values ('" + str(app_id) + "', '" + str(i) + "')")
    svc_iterable = svc_iterable + "\n" + network

    yaml_file = yaml_file if yaml_file is not None else yaml_itr
    f = open(yaml_file, "w")
    f.write(clean_yaml(svc_iterable))
    f.close()
    
def info_app_not_found(command):
    print(f'''No found application to {command}.
To start an application, prepare the docker-compose.yaml.template file and run the following command:
{app_name} create app your-app-name -p external_port:internal_port:statistic_port --replicas=number_backend_server
Example: create app hello-world -p 81:80:82 --replicas=10''')
    
def app_createdb(app):
    if check_arg("-fo"): db_reset()
    row_app = db_execute("select * from tb_app where name = '" + app + "'")
    if len(row_app)==0:
        ports = known_args["ports"]
        if ports is None: ports = "80:80:8040"
        
        # load docker-compose.yaml.template or supplied file
        image = get_arg_after("-i")
        if image is not None:
            tpl_dc = tpl_default
            tpl_dc = tpl_dc.replace("${image}", image)
        else:
            file_dc = get_arg_after("-f")
            file_dc = file_dc if file_dc is not None else "docker-compose.yaml.template"
            f = open(file_dc, 'r')
            tpl_dc = f.read()
        
        # create app record
        db_execute("insert into tb_app (name, ports, tpl_dc) values ('" \
            + app + "', '" + ports + "', '" + db_escape_field(tpl_dc) + "')")
        row = db_select("tb_app", "name", app)
        app_id = row[0]
        
        # create proxy yaml
        create_proxy_service(app_id)
        
        # create non iterable yaml
        create_service_non_iterable(app_id)
        
        # create worker container record
        list_resp = run_docker_command("ps -a -f \"name=^" + app + "-([0-9]+$)\" --format {{.Names}}")
        ar_no = []
        for resp in list_resp:
            ar_no.append(int(resp[len(app + "-"):]))
        ar_no.sort()
        for no in ar_no:
            db_execute("insert into tb_ctn (app_id, no) values ('" + str(app_id) + "', '" + str(no) + "')")
            
        # create iterable yaml
        create_service_iterable(app_id, None, None, min(ar_no), max(ar_no))
        
        # recreate cfg
        update_haproxy_cfg(app_id)
        
        print("Application database is successfully created!")
    else:
        print("There is already application named " + row_app[0][1] + " existed in this directory")
        print("Run \"" + app_name + " start\" to start " + row_app[0][1] + " application now")

def app_create(app):
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app)==0:
        ports = known_args["ports"]
        if ports is None: ports = "80:80:8040"
        replicas = int(known_args["replicas"])
        
        # load docker-compose.yaml.template or supplied file
        image = get_arg_after("-i")
        if image is not None:
            tpl_dc = tpl_default
            tpl_dc = tpl_dc.replace("${image}", image)
        else:
            file_dc = get_arg_after("-f")
            file_dc = file_dc if file_dc is not None else "docker-compose.yaml.template"
            f = open(file_dc, 'r')
            tpl_dc = f.read()
        
        # create app record
        db_execute("insert into tb_app (name, ports, tpl_dc) values ('" \
            + app + "', '" + ports + "', '" + db_escape_field(tpl_dc) + "')")
        row = db_select("tb_app", "name", app)
        app_id = row[0]
        
        # prepare replace var
        update_obj_replace(app_id)
        
        # create service proxy
        create_proxy_service(app_id)
        
        # create service non iterable
        create_service_non_iterable(app_id)
        
        # create service iterable
        create_service_iterable(app_id, replicas)
        
        # create config haproxy.cfg
        update_haproxy_cfg(app_id)
        
        # create network
        network_create(app)
        
        # get non iterable container for checking purpose 
        ctn_non_iterable = get_non_iterable_container_tpl(tpl_dc)
        ctn_non_iterable = clean_yaml(ctn_non_iterable)
        
        # docker compose all
        ## proxy service
        docker_compose(yaml_proxy, "-d", True)
        
        ## non iterable service
        if ctn_non_iterable != '':
            docker_compose(yaml_non_itr, "-d", True)
            
        # get main container image
        tpl_ctn = get_iterable_container_tpl(tpl_dc).replace("${no}", str(1))
        
        image = search_yaml_value(tpl_ctn, "image")
        if image!="":
            # pull newer image, if exists
            old_digest = docker_get_digest(image)
            docker_pull(image)
            new_digest = docker_get_digest(image)
            if new_digest != old_digest:
                print("Application will be using new image")
        
        ## iterable container service
        docker_compose(yaml_itr, "-d", True)
        print("Application successfully deployed!")
    else:
        print("There is already application named " + row_app[0][1] + " existed in this directory")

def app_start(scale=False):
    row = db_execute("select * from tb_app limit 0,1")
    if len(row)==1:
        print("Starting application " + row[0][1])
        f_status = " -f \"status=created\"" if scale else ""
        resp = run_docker_command("ps -a -f \"name=^" + row[0][1] + "-*\" --format {{.Names}}" + f_status)
        if(len(resp)>0):
            for container in resp:
                print("Starting app resource " + container)
                resp = run_docker_command("start " + container)
                if resp == "":
                    print("Failed!")
            if not scale: print("Application " + row[0][1] + " has been started!\nTo stop app simply run \"" + app_name + " stop\"")
        else:
            print("Application's resources not found, you may have deleted them manually. Run \"" + app_name + " delete\" to fully delete your application")
    else:
        info_app_not_found("start")

def app_stop():
    row = db_execute("select * from tb_app limit 0,1")
    if len(row)==1:
        print("Stopping application " + row[0][1])
        resp = run_docker_command("ps -a -f \"name=^" + row[0][1] + "-*\" --format {{.Names}}")
        if(len(resp)>0):
            for container in resp:
                print("Stopping app resource " + container)
                resp = run_docker_command("stop " + container)
                if resp == "":
                    print("Failed!")
            print("Application " + row[0][1] + " has been stopped!\nTo start app simply run \"" + app_name + " start\"\nTo delete app, run \"" + app_name + " delete\"")
        else:
            print("Application's resources not found, you may have deleted them manually. Run \"" + app_name + " delete\" to fully delete your application")
    else:
        info_app_not_found("stop")

def stop_delete_container(container):
    resp = run_docker_command("stop " + container)
    if len(resp)>0:
        if resp[0] != "":
            resp = run_docker_command("rm " + container)
            if len(resp)>0:
                if resp[0] != "":
                    return resp[0]
    return ""

def db_reset():
    db_execute("delete from tb_ctn")
    db_execute("delete from sqlite_sequence where name='tb_ctn'")
    db_execute("delete from tb_app")
    db_execute("delete from sqlite_sequence where name='tb_app'")

def app_reset():
    db_reset()
    print("Application database has been reset")
    
def app_delete():
    row = db_execute("select * from tb_app limit 0,1")
    if len(row)==1:
        app = row[0][1]
        resp = run_docker_command("ps -a -f \"name=^" + app + "-*\" --format {{.Names}}")
        if(len(resp)>0):
            for container in resp:
                print("Deleting app resource " + container)
                resp = stop_delete_container(container)
                if resp == "":
                    print("Failed!")
        print("Deleting app network " + app + "-net")
        resp = run_docker_command("network rm " + app + "-net")
        if len(resp)>0:
            if resp == "":
                print("Failed!")
        
        # delete record
        print("Deleting app data")
        
        # JOIN DB MODE
        # db_execute("delete from tb_ctn where app_id = '" + str(row[0][0]) + "'")
        # db_execute("delete from tb_app where id = '" + str(row[0][0]) + "'")
        
        # LOCAL DB MODE
        db_reset()
        
        print("Application " + app + " has been deleted!")
    else:
        info_app_not_found("delete")

def app_scale():
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app)==1:
        app = row_app[0][1]
        row = db_select("tb_app", "name", app)
        if len(row)>=1:
            app_id = row[0]
            print("Application exists, scaling is possible")
            
            old_replicas = db_execute("select count(*) as num from tb_ctn where app_id = '" + str(app_id) + "'")[0][0]
            new_replicas = int(known_args["replicas"])
            
            if(new_replicas > old_replicas):
                print("Performing up scale...")
                
                # update replace var
                update_obj_replace(app_id)
                
                # create iterable container
                create_service_iterable(app_id, (new_replicas - old_replicas))
                
                # compose new container
                docker_compose(yaml_itr, "-d", True)
                
                #refresh service
                refresh_service(app_id)
                
                print("App backed server has been up-scaled into " + str(new_replicas))
        
            elif(new_replicas < old_replicas):
                
                print("Performing down scale...")
                
                # update replace var
                update_obj_replace(app_id)
                
                # delete first container
                delete_n_first_container(app_id, old_replicas - new_replicas)
                
                #refresh service
                refresh_service(app_id)
                
                print("App backed server has been down-scaled into " + str(new_replicas))
    else:
        info_app_not_found("scale")

def check_container(name):
    resp = run_docker_command("ps -a -f \"name=" + name + "\" --format {{.ID}}")
    return len(resp)>0

def search_yaml_value(string_yaml, search_key):
    dct = yaml.safe_load(string_yaml)
    
    for key in dct:
        for key1 in dct[key]:
            if key1==search_key:
                return dct[key][key1]
    return ""

def docker_get_digest(repo):
    resp = run_docker_command("inspect " + repo + " | " + ("findstr" if os.name=="nt" else "grep")  + " -i " + repo + "@sha256")
    if len(resp)>0:
        str_resp = resp[0].replace(" ","")
        if str_resp != "":
            ar_resp = str_resp.split(":")
            return ar_resp[1].rstrip(",")
    return ""

def docker_pull(repo):
    subprocess.call(["docker", "pull", repo])

def docker_check_image_new(repo):
    docker_pull(repo)
    resp = run_docker_command("pull " + repo)
    # print(resp)
    for line in resp:
        ar_line = line.split(":")
        if len(ar_line)>1:
            if ar_line[0]=="Status":
                chk = "Downloaded newer image"
                txt = ar_line[1].strip()
                if txt[:len(chk)]==chk:
                    return True
    return False
    
def app_update():
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app)==1:
        app_id = row_app[0][0]
        app = row_app[0][1]
        tpl_dc = row_app[0][3]
        
        # get main container image
        dc = replace_variable(tpl_dc)
        ar_dc = dc.split("### ITERABLE CONTAINER BLOCK ###")
        ctn_iterable1 = ar_dc[1].replace("${no}", str(1))
        
        image = search_yaml_value(ctn_iterable1, "image")
        if image!="":
            
            # check and automatically download image
            old_digest = docker_get_digest(image)
            docker_pull(image)
            new_digest = docker_get_digest(image)
            
            if new_digest != old_digest or check_arg("-fo"):
                print("Updating application " + app)
                if(get_arg_after("-st")=='1b1'):
                    print("Update strategy will be done one by one: new 1 up, old 1 down, etc until all container updated")
                    
                    print("Continue update? (y / n)")
                    resp = input()
                    if resp!='y': sys.exit(0)
                    
                    rows = db_execute("SELECT id, no from tb_ctn where app_id = '" + str(app_id) + "' ORDER by no")
                    
                    for row in rows:
                        # delete 1 first container
                        delete_n_first_container(app_id, 1)
                        
                        # create 1 new container
                        create_service_iterable(app_id, 1)
                        
                        # deploy new container
                        docker_compose(yaml_itr, "-d", True)
                        
                        #refresh service
                        refresh_service(app_id)
                    
                else:
                    print("Update strategy will be done half by half: old 25% down, new 50% up, old 75% down, new 50% up")
                    
                    replicas = db_execute("select count(*) as num from tb_ctn where app_id = '" + str(app_id) + "'")[0][0]
                    
                    # get 25% to down and 50% to add
                    num_del = math.floor(replicas*0.25)
                    num_add = math.ceil(replicas*0.5)
                
                    # if image is new then proceed update
                    print("Continue update? (y / n)")
                    resp = input()
                    if resp!='y': sys.exit(0)
                    
                    # delete 25% first container
                    delete_n_first_container(app_id, num_del)
                    
                    #refresh service
                    refresh_service(app_id)
                    
                    # create 50% new container
                    create_service_iterable(app_id, num_add)
                    
                    # deploy container & update config
                    docker_compose(yaml_itr, "-d", True)
                    
                    #refresh service
                    refresh_service(app_id)
                    
                    # once the routine is entering here, it means already running
                    # so, delete the first 8 and replace with 5 new
                    delete_n_first_container(app_id, replicas-num_del)
                    
                    #refresh service
                    refresh_service(app_id)
                    
                    # add 50% rest iterable service
                    create_service_iterable(app_id, replicas-num_add)
                    
                    # deploy container & update config
                    docker_compose(yaml_itr, "-d", True)
                    
                    #refresh service
                    refresh_service(app_id)
                    
                print("Updating app " + app + " completed!")
                
            else:
                print("Image is already up to date. Skipped")
        else:
            print("Image not found in the YAML template file, cannot update")
        
    else:
        info_app_not_found("update")
        
def remove_double_space(txt):
    x = re.search("  ", txt)
    while x:
        txt = txt.replace("  ", " ")
        x = re.search("  ", txt)
    return txt

def app_top():
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app)==1:
        app_id = row_app[0][0]
        app = row_app[0][1]
        list_resp = run_docker_command("stats --no-stream --format \"table {{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.MemUsage}}\"")
        total_cpu = 0.00
        total_mem = 0.00
        list_resp_new =  []
        for resp in list_resp:
            ar = remove_double_space(resp).split(" ")
            if ar[0]=="NAME":
                list_resp_new.append([-1, resp])
            elif re.search("^" + app + "-*", ar[0]):
                str_no = ar[0][len(app + "-"):]
                if str_no=="proxy":
                    list_resp_new.append([0, resp])
                    total_cpu = total_cpu + float(ar[1].replace("%",""))
                    total_mem = total_mem + float(ar[2].replace("%",""))
                else:
                    list_resp_new.append([int(str_no), resp])
                    total_cpu = total_cpu + float(ar[1].replace("%",""))
                    total_mem = total_mem + float(ar[2].replace("%",""))
        
        list_resp_new.sort()
        for resp in list_resp_new:
            print(resp[1])
        
        print("\nSUMMARY")
        print("CPU %\tMEM %")
        print("" + str(total_cpu)[:5] + "%\t" + str(total_mem)[:5] + "%")
        print("")
    else:
        info_app_not_found("get info")
        
def app_proc():
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app)==1:
        app = row_app[0][1]
        list_resp = run_docker_command("ps -a -f \"name=" + app + "-*\" --format \"table {{.Names}}\\t{{.Ports}}\\t{{.Status}}\\t{{.RunningFor}}\"")
        list_resp_new =  []
        for resp in list_resp:
            ar = remove_double_space(resp).split(" ")
            if ar[0]=="NAMES":
                list_resp_new.append([-1, resp])
            else:
                str_no = ar[0][len(app + "-"):]
                if str_no=="proxy":
                    list_resp_new.append([0, resp])
                else:
                    list_resp_new.append([int(str_no), resp])
        
        list_resp_new.sort()
        for resp in list_resp_new:
            print(resp[1])
        
        print("")
    else:
        info_app_not_found("get info")
        
def app_exec():
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app)==1:
        app = row_app[0][1]
        if get_arg(2)!="":
            params = ["docker", "exec", "-it", app + "-" + get_arg(2)]
            i = -1
            for arg in args:
                i = i + 1
                if i > 2:
                    params.append(arg)
            if check_arg("-d"): print("Running: " + str(params))
            subprocess.call(params)
    else:
        info_app_not_found("bash")
        
def app_logs():
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app)==1:
        app_id = row_app[0][0]
        if get_arg(2)=='--proxy':
            # create proxy docker compose file
            create_proxy_service(app_id, yaml_logs)
        elif get_arg(2)=='--worker':
            if get_arg(3)=='':
                tmp_row = db_execute("select ifnull(min(no),0) as min_no, ifnull(max(no),0) as max_no from tb_ctn where app_id = '" + str(app_id) + "'")
                ar_no = []
                ar_no.append(tmp_row[0][0])
                ar_no.append(tmp_row[0][1])
            else:
                ar_no = get_arg(3).split(":")
                if len(ar_no)==1:
                    ar_no.append(ar_no[0])
            create_service_iterable(app_id, int(ar_no[1])-int(ar_no[0]) + 1, yaml_logs, int(ar_no[0]), int(ar_no[1]))
        else:
            # create full docker compose file
            create_service_full(app_id, yaml_logs)
        
        # execute docker compose up
        print("Please do not press CTRL + C to prevent containers from stopping. Close the window instead!")
        print("Continue? (y / n)")
        r = input()
        if(r=='y'):
            docker_compose(yaml_logs, "", True)
    else:
        info_app_not_found("get info")
        
def app_docker():
    params = ["docker"]
    i = -1
    for arg in args:
        i = i + 1
        if i > 1:
            params.append(arg)
    if check_arg("-d"): print("Running: " + str(params))
    subprocess.call(params)

# capture CTRL + C
signal.signal(signal.SIGINT, signal_handler)

# get args
str_args = " ".join(sys.argv).replace("=", " ")

# simplify args
args1 = str_args.split(" ")
args = []
for arg in args1:
    if arg=='--debug': arg = '-d'
    if arg=='--port': arg = '-p'
    if arg=='--replicas': arg = '-r'
    if arg=='--interactive': arg = '-i'
    if arg=='--start': arg = '-s'
    if arg=='--strategy': arg = '-st'
    if arg=='--force-update': arg = '-fu'
    if arg=='--file': arg = '-f'
    if arg=='--version': arg = '-v'
    if arg=='--force': arg = '-fo'
    args.append(arg)

# known args
known_args = {}
known_args["app"] = get_arg_after("-a")
known_args["ports"] = get_arg_after("-p")
known_args["replicas"] = get_arg_after("-r")
known_args["file"] = get_arg_after("-f")

# debug args
if check_arg("-d"):
    print("Passed Arguments: " + str(args))

app_title = "AMProxy"
app_name = "amproxy"

tpl_proxy = '''
    ${app}-proxy:
        image: haproxytech/haproxy-alpine:2.4
        container_name: ${app}-proxy
        restart: always
        ports:
            - ${external_port}:80
            - ${statistic_port}:8404
        volumes:
            - ./auto_generated/cfg:/usr/local/etc/haproxy:ro
'''

tpl_network = '''
networks:
    ${app}-net:
        external: true
'''

tpl_cfg = '''
global
    stats socket /var/run/api.sock user haproxy group haproxy mode 660 level admin expose-fd listeners
    log stdout format raw local0 info

defaults
    mode http
    timeout client 600s
    timeout connect 600s
    timeout server 600s
    timeout http-request 600s
    log global

frontend stats
    bind *:8404
    stats enable
    stats uri /
    stats refresh 10s

frontend ${app}-frontend
    bind :80
    default_backend ${app}-backend

backend ${app}-backend
'''

tpl_default = '''
---
services:
### NON ITERABLE CONTAINER BLOCK ###
### ITERABLE CONTAINER BLOCK ###
    ${app}-${no}:
        image: ${image}
        container_name: ${app}-${no}
        restart: always
        extra_hosts:
            - "host.docker.internal:host-gateway"
'''

tpl_container_network = get_indent(2) + "networks:\n" + get_indent(3) + "- ${app}-net"
tpl_backend_server = "server s${no} ${app}-${no}:${container_port} check"

# prepare directory
# print(os.getcwd())
tmpdir = "auto_generated"
dir_cfg = tmpdir + "/cfg"
dir_db = tmpdir + "/db"
file_db = dir_db + "/" + app_name + ".db"

# temp yaml
yaml_proxy = "_proxy.yaml"
yaml_non_itr = "_non_itr.yaml"
yaml_itr = "_itr.yaml"
yaml_full = "docker-compose.yaml"
yaml_logs = "_logs.yaml"

if not (get_arg(1)=="-v" or get_arg(1)=="docker" or get_arg(1)==""):
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)        
    if not os.path.exists(dir_cfg):
        os.mkdir(dir_cfg)
    if not os.path.exists(dir_db):
        os.mkdir(dir_db)

# prepare database

if not (get_arg(1)=="-v" or get_arg(1)=="docker" or get_arg(1)==""):
    if not os.path.exists(file_db):
        conn = sqlite3.connect(file_db)
        conn.execute('''CREATE TABLE tb_app
                    (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name            CHAR(255),
                        ports           CHAR(50),
                        tpl_dc          TEXT
                    );''')
        conn.execute("CREATE INDEX app_idx_name ON tb_app (name);")
        conn.execute('''CREATE TABLE tb_ctn
                    (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        app_id  INT,
                        no      INT
                    );''')
        conn.execute("CREATE INDEX container_idx_app_id ON tb_ctn (app_id);")
        conn.execute("CREATE INDEX container_idx_app_id_no ON tb_ctn (app_id, no);")
        conn.close()

obj_replace = {}

if len(args)>=2:
    if args[1]=="create": app_create(args[2])
    elif args[1]=="createdb": app_createdb(args[2])
    elif args[1]=="start": app_start()
    elif args[1]=="stop": app_stop()
    elif args[1]=="delete": app_delete()
    elif args[1]=="scale": app_scale()        
    elif args[1]=="update": app_update()
    elif args[1]=="reset": app_reset()
    elif args[1]=="proc": app_proc()
    elif args[1]=="top": app_top()
    elif args[1]=="logs": app_logs()
    elif args[1]=="exec": app_exec()
    elif args[1]=="docker": app_docker()
    elif args[1]=="digest":
        if get_arg(2)!="":
            digest = docker_get_digest(get_arg(2))
            print(digest)
    elif args[1]=="-v":
        version = "v1.0.19"
        version_comment = "create directly start"

        print("AMProxy " + version)
        print("Version Comment: " + version_comment)
        print("License: GNU General Public License v3")
        print("Author: Aris Munawar, S. T., M. Sc.")
        print("Repositories:")
        print("- Medium: https://medium.com/@areesmoon")
        print("- Github: https://github.com/areesmoon/")
        print("- Docker: https://hub.docker.com/u/areesmoon")
    else: print(f'''
AMProxy is an easy to use manageable load balancer for multiple docker containers. It utilizes HAProxy inside the lightweight linux alpine distribution docker image.

To start an application, edit the existing docker-compose.yaml.template template file and run the following command:
{app_name} create app your-app-name -p external_port:internal_port:statistic_port --replicas=number_of_backend_server

Example: {app_name} create app hello-world -p 81:80:82 --replicas=10

Available commands:
create      Create the application, see the above example
            - options: --image, --replicas --port
createdb    Create application database from a running application
            - options: --image, --port
digest      Get SHA256 digest from a docker repo
            Example:
            - {app_name} digest php:alpine
exec        Run command inside worker container or proxy container
            - option: proxy, worker_no
            Example:
            - {app_name} exec 5 bash (this will run bash inside container app-name-5)
start       Start the already created application
stop        Stop currently running application
scale       Scale up / down the running application
            - options: -r / --replicas
            Example:
            - {app_name} scale hello-world --replicas=20
update      Update container with the newest image, done half by half
            - options: -fo / --force
delete      To delete the application and all resources
reset       Reset application database (containers must be deleted manually)
proc        To show running instance of backend service
top         To show CPU and memory usage by all resources
docker      To run any docker's related command (followed by docker related command's parameters)
logs        To see log of the running process
            - options: --proxy, --worker [worker_no]:[worker_no]
            Example:
            - {app_name} logs --proxy (to see proxy logs)
            - {app_name} logs --worker 2:5 (to see log worker no 2 to 5)

Available parameters:
-d, --debug         Show command run by AMProxy internal process for debug purpose
-f, --file [file]   Specify custom yaml file
-fo, --force        Force update even if the image is not new (used with update)
-i, --image         Container's docker image (direct app creation without docker-compose.yaml.template)
-p, --port          Ports setting, consists of three ports, external_port:internal_port:statistic_port
                    - external_port: externally accessible port for your application service
                    - internal_port: internal / service container port (for http usually 80)
                    - statistic_por: externally accessible port for load balancer statistic
-r, --replicas      Number of backend server instances
-s, --start         To directly start application after created
-st, --strategy     Update strategy:
                    - hbh: half by half (default, container will be replace 50% by 50%)
                    - 1b1: one by one (container will be updated 1 by 1)
-v, --version       Show current application version

Upon started, your application is available at the following URL:
- Application service: http://localhost:external_port
- Load balancing statistic: http://localhost:statistic_port
''')
else:
    print("No argument supplied")