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
import argparse
from .version import __version__, __commit__, __released__

# NOTE:
# if error running executable binary, run to fix:
# sudo mount /tmp -o remount,exec

# ================================== #
# ========== Declarations ========== #
# ================================== #

# args
parser = None
args = None
obj_replace = {}

app_title = "AMProxy"
app_name = "amproxy"

# prepare directory
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

tpl_proxy = '''
    ${app}-proxy:
        image: haproxytech/haproxy-alpine
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

tpl_container_network = "        " + "networks:\n" + "            " + "- ${app}-net"
tpl_backend_server = "server s${no} ${app}-${no}:${container_port} check"


# ================================== #
# =========== Functions ============ #
# ================================== #


def signal_handler(sig, frame):
    sys.exit(0)

def db_escape_field(field):
    return field.replace("'", "''")

def db_execute(query):
    if args.debug: print("Running query: " + query)
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
    if args.debug: print("Running query: " + query)
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

def get_app():
    return args.app_name

def get_app_prefix(app):
    return app + '-'

def list2json(list):
    str_resp = ''.join(map(str, list))
    return json.loads(str_resp)

def run_command(command, attach = False):
    if args.debug: print("Running command: {}".format(command))
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
    
def app_network_create(app):
    resp = run_docker_command("network create --driver=bridge " + get_app_prefix(app) + 'net')
    if resp==[]:
        print("Network " + get_app_prefix(app) + 'net' + " already existed")
    else:
        print("Network " + get_app_prefix(app) + 'net' + " is created")
    
def app_network_get(app):
    resp = run_docker_command("network inspect " + get_app_prefix(app) + 'net')
    print_json(list2json(resp))
    
def app_network_delete(app):
    resp = run_docker_command("network rm " + get_app_prefix(app) + 'net')
    if(resp==[]):
        print("Network not found")
    elif(resp[0]==get_app_prefix(app) + 'net'):
        print("Network " + get_app_prefix(app) + 'net' + " is deleted")
        
def network_delete(network_name):
    resp = run_docker_command("network rm " + network_name)
    if(resp==[]):
        print("Network not found")
    elif(resp[0]==network_name):
        print("Network " + network_name + " is deleted")

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
    
def get_ports(container_name):
    result = subprocess.run(["docker", "port", container_name], capture_output=True, text=True)
    output = result.stdout.strip().splitlines()

    external_port = None
    internal_port = None
    statistic_port = None

    for line in output:
        match = re.match(r"(\d+)/tcp -> .*:(\d+)", line)
        if match:
            internal = int(match.group(1))
            external = int(match.group(2))
            if internal == 80:
                internal_port = internal
                external_port = external
            elif internal == 8404:
                statistic_port = external

    return str(external_port) + ":" + str(internal_port) + ":" + str(statistic_port)

def get_top_app_container_name(app):
    cmd = f'ps -a -f "name=^{app}-([0-9]+$)" --format "{{{{.Names}}}}"'
    list_resp = run_docker_command(cmd)
    return list_resp[0] if len(list_resp) > 0 else None

def get_top_app_container_image(app):
    cmd = f'ps -a -f "name=^{app}-([0-9]+$)" --format "{{{{.Image}}}}"'
    list_resp = run_docker_command(cmd)
    return list_resp[0] if len(list_resp) > 0 else None
    
def app_createdb():
    app = args.app_name
    if args.force: db_reset()
    row_app = db_execute("select * from tb_app where name = '" + app + "'")
    if len(row_app)==0:
        ports = get_ports(app + "-proxy")
        if ports is None: ports = "80:80:8040"
        
        # load docker-compose.yaml.template or supplied file
        image = get_top_app_container_image(app)
        if image is not None:
            tpl_dc = tpl_default
            tpl_dc = tpl_dc.replace("${image}", image)
        else:
            file_dc = args.file
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
        # for no in ar_no:
        #    db_execute("insert into tb_ctn (app_id, no) values ('" + str(app_id) + "', '" + str(no) + "')")
            
        # create iterable yaml
        create_service_iterable(app_id, None, None, min(ar_no), max(ar_no))
        
        # recreate cfg
        update_haproxy_cfg(app_id)
        
        print("Application database is successfully created!")
    else:
        print("There is already application named " + row_app[0][1] + " existed in this directory")
        print("Run \"" + app_name + " start\" to start " + row_app[0][1] + " application now")

def app_create():
    app = args.app_name
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app)==0:
        ports = args.port
        if ports is None: ports = "80:80:8040"
        replicas = args.replicas
        
        # load docker-compose.yaml.template or supplied file
        image = args.image
        if image is not None:
            tpl_dc = tpl_default
            tpl_dc = tpl_dc.replace("${image}", image)
        else:
            file_dc = args.file
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
        app_network_create(app)
        
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
        resp = run_docker_command("ps -a -f \"name=^" + row[0][1] + "-[^-]+$\" --format {{.Names}}" + f_status)
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
        resp = run_docker_command("ps -a -f \"name=^" + row[0][1] + "-[^-]+$\" --format {{.Names}}")
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
            resp = run_docker_command("rm --volumes " + container)
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
    
def get_container_network_name(container_name):
    output = run_docker_command(
        f"inspect -f '{{{{json .NetworkSettings.Networks}}}}' {container_name}"
    )
    if output:
        networks = json.loads(output[0])
        return list(networks.keys())[0] if networks else None
    return None

def app_delete():
    row = db_execute("select * from tb_app limit 0,1")
    if len(row)==1:
        app = row[0][1]
        
        resp = run_docker_command("ps -a -f \"name=^" + app + "-[^-]+$\" --format {{.Names}}")
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
            new_replicas = args.replicas
            
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

def app_digest():
    digest = docker_get_digest(args.image)
    print(digest)

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
            
            if new_digest != old_digest or args.force:
                print("Updating application " + app)
                if(args.strategy=='1b1'):
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
            elif re.search("^" + app + "-[^-]+$", ar[0]):
                str_no = ar[0][len(app + "-"):]
                if str_no.isnumeric():
                    list_resp_new.append([int(str_no), resp])
                    total_cpu = total_cpu + float(ar[1].replace("%",""))
                    total_mem = total_mem + float(ar[2].replace("%",""))
                else:
                    list_resp_new.append([0, resp])
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
        
def app_ps():
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app)==1:
        app = row_app[0][1]
        list_resp = run_docker_command("ps -a -f \"name=" + app + "-[^-]+$\" --format \"table {{.Names}}\\t{{.Ports}}\\t{{.Status}}\\t{{.RunningFor}}\"")
        list_resp_new =  []
        for resp in list_resp:
            ar = remove_double_space(resp).split(" ")
            if ar[0]=="NAMES":
                list_resp_new.append([-1, resp])
            else:
                str_no = ar[0][len(app + "-"):]
                if str_no.isnumeric():
                    list_resp_new.append([int(str_no), resp])
                else:
                    list_resp_new.append([0, resp])
        
        list_resp_new.sort()
        for resp in list_resp_new:
            print(resp[1])
        
        print("")
    else:
        info_app_not_found("get info")
        
def app_exec():
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app) == 1:
        app_name = row_app[0][1]
        container_name = f"{app_name}-{args.worker_no}"
        params = ["docker", "exec", "-it", container_name] + args.docker_args
        if args.debug:
            print("Running:", " ".join(params))
        subprocess.call(params)
    else:
        info_app_not_found("bash")
        
def app_logs():
    row_app = db_execute("SELECT * FROM tb_app LIMIT 1")
    if len(row_app) != 1:
        info_app_not_found("get info")
        return

    app_id = row_app[0][0]

    if args.proxy:
        create_proxy_service(app_id, yaml_logs)

    elif args.worker:
        if args.range is None:
            tmp_row = db_execute(
                f"SELECT IFNULL(MIN(no),0), IFNULL(MAX(no),0) FROM tb_ctn WHERE app_id = '{app_id}'"
            )
            min_no, max_no = tmp_row[0][0], tmp_row[0][1]
        else:
            try:
                parts = args.range.split(":")
                if len(parts) == 1:
                    min_no = max_no = int(parts[0])
                else:
                    min_no = int(parts[0])
                    max_no = int(parts[1])
            except:
                print("Invalid range format. Use format like 0:5 or 3.")
                return

        total = max_no - min_no + 1
        create_service_iterable(app_id, total, yaml_logs, min_no, max_no)

    else:
        create_service_full(app_id, yaml_logs)

    print("Please do not press CTRL + C to prevent containers from stopping. Close the window instead!")
    print("Continue? (y / n)")
    r = input().strip().lower()
    if r == 'y':
        docker_compose(yaml_logs, "", True)
        
def app_docker(docker_args, debug=False):
    params = ["docker"] + docker_args
    if debug:
        print("Running:", " ".join(params))
    subprocess.call(params)

def app_version():
    return f"""
=====================================================
                      {app_title}
=====================================================
Version: {__version__}
Commit: {__commit__}
Released: {__released__}
License: GNU General Public License v3
Author: Aris Munawar, S. T., M. Sc.
-----------------------------------------------------
Profile & Repositories:
- LinkedIn: https://www.linkedin.com/in/aris-munawar/
- Medium  : https://medium.com/@areesmoon
- GitHub  : https://github.com/areesmoon/
- Docker  : https://hub.docker.com/u/areesmoon
"""

def main():
    # capture CTRL + C
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(
        prog="amproxy",
        description=f"""
=======================================================================================
                                {app_title} - {__version__}
---------------------------------------------------------------------------------------
                      Load balancer for multiple docker containers
=======================================================================================
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # debug flag
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")

    # version flag
    parser.add_argument("-v", "--version", action="store_true", help="Show version info")
    
    # subparsers
    subparsers = parser.add_subparsers(dest="command")

    # create command
    create_parser = subparsers.add_parser(
        "create",
        help="Create the application",
        description="""Create the application

example:
  amproxy create hello-world -p 81:80:82 --replicas=10""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    create_parser.add_argument("app_name", help="Name of the application")
    create_parser.add_argument("-p", "--port", help="Ports in format external:internal:statistic")
    create_parser.add_argument("-r", "--replicas", type=int, help="Number of backend server instances")
    create_parser.add_argument("-i", "--image", help="Container docker image")
    create_parser.add_argument("-f", "--file", help="Custom YAML file to use")
    create_parser.add_argument("-s", "--start", action="store_true", help="Start application after create")
    create_parser.set_defaults(func=app_create)

    # createdb command
    createdb_parser = subparsers.add_parser("createdb",
        help="Create database from an already running " + app_title +" application",
        description="Create database from an already running " + app_title + " application"
    )
    createdb_parser.add_argument("app_name", help="Name of the application")
    createdb_parser.add_argument("-fo", "--force", action="store_true", help="Force reset application database")
    createdb_parser.add_argument("-f", "--file", help="Custom YAML file to use")
    createdb_parser.set_defaults(func=app_createdb)

    # start command
    start_parser = subparsers.add_parser("start",
        help="Start the already created application",
        description="Start the already created application"
    )
    start_parser.set_defaults(func=app_start)

    # stop command
    stop_parser = subparsers.add_parser("stop", 
        help="Stop the currently running application",
        description="Stop the currently running application"
    )
    stop_parser.set_defaults(func=app_stop)

    # scale command
    scale_parser = subparsers.add_parser("scale",
        help="Scale up/down a running application",
        description="""Scale up/down a running application

example:
  amproxy scale -r 5""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    scale_parser.add_argument("-r", "--replicas", type=int, required=True, help="Number of replicas")
    scale_parser.set_defaults(func=app_scale)

    # update command
    update_parser = subparsers.add_parser("update",
        help="Update application's containers with newest image",
        description="""Update application's containers with newest image

example:
  amproxy update -fo -st 1b1""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    update_parser.add_argument("-fo", "--force", action="store_true", help="Force update even if image not new")
    update_parser.add_argument("-st", "--strategy", choices=["hbh", "1b1"], default="hbh", help="Update strategy: 'hbh' = half-by-half, '1b1' = one-by-one (rolling)")
    update_parser.set_defaults(func=app_update)
    
    # delete command
    delete_parser = subparsers.add_parser("delete",
        help="To delete an application and its all running container",
        description="To delete an application and its all running container"
    )
    delete_parser.set_defaults(func=app_delete)

    # reset command
    reset_parser = subparsers.add_parser("reset",
        help="Reset application database (containers must be deleted manually)",
        description="Reset application database (containers must be deleted manually)"
        )
    reset_parser.set_defaults(func=app_reset)

    # proc command
    proc_parser = subparsers.add_parser("ps",
        help="To show running instance of backend service",
        description="To show running instance of backend service"
    )
    proc_parser.set_defaults(func=app_ps)

    # top command
    top_parser = subparsers.add_parser("top",
        help="To show CPU and memory usage by all resources",
        description="To show CPU and memory usage by all resources"
    )
    top_parser.set_defaults(func=app_top)

    # logs command
    logs_parser = subparsers.add_parser("logs",
        help="Show interactive logs",
        description="Show interactive logs"
    )
    logs_parser.add_argument("--proxy", action="store_true", help="Use proxy service only")
    logs_parser.add_argument("--worker", action="store_true", help="Use worker service only")
    logs_parser.add_argument("--range", help="Worker range in format MIN:MAX or just a single number")
    logs_parser.set_defaults(func=app_logs)

    # exec command
    exec_parser = subparsers.add_parser("exec",
        help="Run command inside worker or proxy container",
        description="Run command inside worker or proxy container"
    )
    exec_parser.add_argument("worker_no", help="Worker number or 'proxy'")
    exec_parser.add_argument("docker_args", nargs=argparse.REMAINDER, help="Arguments to pass to docker exec (example: bash, sh, etc.)")
    exec_parser.set_defaults(func=app_exec)

    # docker command
    docker_parser = subparsers.add_parser("docker",
        help="Run docker commands",
        description="Run docker commands"
    )
    docker_parser.add_argument("docker_args", nargs=argparse.REMAINDER, help="Arguments for docker")
    docker_parser.set_defaults(func=app_docker)

    # digest command
    digest_parser = subparsers.add_parser("digest", 
        help="Get SHA256 digest from docker repo",
        description="Get SHA256 digest from docker repo"
    )
    digest_parser.add_argument("image", help="Docker image name")
    digest_parser.set_defaults(func=app_digest)

    args = parser.parse_args()
    
    if not (args.version or args.command in ["docker", None]):
        if not os.path.exists(tmpdir):
            os.mkdir(tmpdir)
        if not os.path.exists(dir_cfg):
            os.mkdir(dir_cfg)
        if not os.path.exists(dir_db):
            os.mkdir(dir_db)

    # prepare database
    if not (args.version or args.command in ["docker", None]):
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
            
    if args.debug:
        print("[DEBUG] Args parsed:")
        print(vars(args))
    
    if args.version:
        print(app_version())
        sys.exit()

    if hasattr(args, "func"):
        args.func()
    else:
        parser.print_help()
        
# ================================== #
# ========== Entry Point =========== #
# ================================== #

if __name__ == "__main__":
    main()