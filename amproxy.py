#!/usr/bin/python3
import sys
import subprocess
import json
import os
import sqlite3
import math
import yaml


# NOTE:
# if error running executable binary, run to fix:
# sudo mount /tmp -o remount,exec


def db_escape_field(field):
    return field.replace("'", "''")

def db_execute(query):
    conn = sqlite3.connect(file_db)
    cursor = conn.execute(query)
    rows = []
    for row in cursor:
        rows.append(row)
    conn.commit()
    conn.close()
    return rows
    
def db_select(table, by, field):
    rows = db_execute("select * from " + table + " where " + by + " = '" + str(field) + "'")
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

def run_command(command):
    # print("Running command: {}".format(command))
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    list_resp = p.stdout.readlines()
    new_list_resp = []
    for line in list_resp:
        new_list_resp.append(line.rstrip())
    return new_list_resp

def run_docker_command(command):
    return run_command("docker " + command)

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

def docker_compose(file, option="", attach_process=False):
    if(attach_process):
        if option!="":
            subprocess.call(["docker", "compose", "-f", file,  "up", option])
        else:
            subprocess.call(["docker", "compose", "-f", file,  "up"])
    else:
        return run_docker_command("compose -f " + file + " up " + (" " + option if option != "" else option))
    
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
        
def update_obj_replace(app, ports):
    obj_replace["app"] = app
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
            print("Success!")
            db_execute("DELETE FROM tb_ctn WHERE id = '" + str(row[0]) + "'")
        else:
            print("Failed!")

def update_haproxy_cfg(app_id):
    cfg = clean_yaml(tpl_cfg)
    rows = db_execute("SELECT no from tb_ctn where app_id = '" + str(app_id) + "'")
    if len(rows) > 0:
        for row in rows:
            cfg = cfg + "\n    " + tpl_backend_server.replace("${no}", str(row[0]))
    cfg = replace_variable(cfg)
    f = open(dir_cfg + "/" + "haproxy.cfg", "w")
    f.write(cfg + "\n")
    f.close()
    
def create_proxy_service():
    proxy= replace_variable(tpl_proxy)
    container_network = replace_variable(tpl_container_network)
    network = replace_variable(tpl_network)
        
    svc_proxy = "services:\n" + proxy + "\n" + container_network + "\n" + network
    f = open(yaml_proxy, "w")
    f.write(clean_yaml(svc_proxy))
    f.close()
    
def create_non_iterable_service(app_id):
    row_app = db_select("tb_app", "id", app_id)
    app = row_app[1]
    tpl_dc = row_app[3]
    
    #update variable
    update_obj_replace(app, row_app[2])
    
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
    
def create_iterable_service(app_id, n):
    row_app = db_select("tb_app", "id", app_id)
    app = row_app[1]
    tpl_dc = row_app[3]
    
    #update variable
    update_obj_replace(app, row_app[2])
    
    # prepare template
    container_network = replace_variable(tpl_container_network)
    network = replace_variable(tpl_network)
    
    # get main container image
    ctn_iterable = get_iterable_container_tpl(tpl_dc)
    
    # max cotainer's no
    max_no = db_execute("select ifnull(max(no),0)  as max_no from tb_ctn where app_id = '" + str(app_id) + "'")[0][0]
    
    # create service iterable
    svc_iterable = "services:\n"
    for i in range(max_no + 1, max_no + n + 1):
        svc_iterable = svc_iterable + "\n" + ctn_iterable.replace("${no}", str(i)) + "\n" + container_network
        db_execute("insert into tb_ctn (app_id, no) values ('" + str(app_id) + "', '" + str(i) + "')")    
    svc_iterable = svc_iterable + "\n" + network

    f = open(yaml_itr, "w")
    f.write(clean_yaml(svc_iterable))
    f.close()
    
def info_app_not_found(command):
    print(f'''No found application to {command}.
To start an application, prepare the docker-compose.yaml file and run the following command:
{app_name} create app your-app-name -p external_port:internal_port:statistic_port --replicas=number_backend_server
Example: create app hello-world -p 81:80:82 --replicas=10''')

def app_create(app):
    row_app = db_execute("select * from tb_app limit 0,1")
    if len(row_app)==0:
        ports = known_args["ports"]
        if ports is None: ports = "80:80:8040"
        replicas = int(known_args["replicas"])
        
        # load docker-compose.yaml or supplied file
        file_dc = get_arg_after("-f")
        file_dc = file_dc if file_dc is not None else "docker-compose.yaml"
        f = open(file_dc, 'r')
        tpl_dc = f.read()
        
        # create app record
        db_execute("insert into tb_app (name, ports, tpl_dc) values ('" \
            + app + "', '" + ports + "', '" + db_escape_field(tpl_dc) + "')")
        row = db_select("tb_app", "name", app)
        app_id = row[0]
        
        # prepare replace var
        update_obj_replace(app, ports)
        
        # create service proxy
        create_proxy_service()
        
        # create service non iterable
        create_non_iterable_service(app_id)
        
        # create service iterable
        create_iterable_service(app_id, replicas)
        
        # create config haproxy.cfg
        update_haproxy_cfg(app_id)
        
        # create network
        network_create(app)
        
        # get non iterable container for checking purpose 
        ctn_non_iterable = get_non_iterable_container_tpl(tpl_dc)
        ctn_non_iterable = clean_yaml(ctn_non_iterable)
        
        # docker compose all
        ## proxy service
        docker_compose(yaml_proxy, "--no-start")
        
        ## non iterable service
        if ctn_non_iterable != '':
            docker_compose(yaml_non_itr, "--no-start")
        
        ## iterable container service
        if(check_arg('-s')):
            # directly start
            docker_compose(yaml_itr, "", True)
        else:
            docker_compose(yaml_itr, "--no-start", True)
            print("Application successfully deployed!\nRun \"" + app_name + " start\" to start your application now")
    else:
        print("There is already application named " + row_app[0][1] + " existed in this directory")
        print("Run \"" + app_name + " start\" to start " + row_app[0][1] + " application now")
    
def app_start(scale=False):
    row = db_execute("select * from tb_app limit 0,1")
    if len(row)==1:
        print("Starting application " + row[0][1])
        f_status = " -f \"status=created\"" if scale else ""
        resp = run_docker_command("ps -a -f \"name=" + row[0][1] + "-([0-9]|proxy)\" --format {{.Names}}" + f_status)
        if(len(resp)>0):
            for container in resp:
                print("Starting app resource " + container)
                resp = run_docker_command("start " + container)
                if resp != "":
                    print("Success!")
                else:
                    print("Failed!")
            print("Application " + row[0][1] + " has been started!\nTo stop app simply run \"" + app_name + " stop\"")
        else:
            print("Application's resources not found, you may have deleted them manually. Run \"" + app_name + " delete\" to fully delete your application")
    else:
        info_app_not_found("start")

def app_stop():
    row = db_execute("select * from tb_app limit 0,1")
    if len(row)==1:
        print("Stopping application " + row[0][1])
        resp = run_docker_command("ps -a -f \"name=" + row[0][1] + "-([0-9]|proxy)\" --format {{.Names}}")
        if(len(resp)>0):
            for container in resp:
                print("Stopping app resource " + container)
                resp = run_docker_command("stop " + container)
                if resp != "":
                    print("Success!")
                else:
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
    
def app_delete():
    row = db_execute("select * from tb_app limit 0,1")
    if len(row)==1:
        app = row[0][1]
        resp = run_docker_command("ps -a -f \"name=" + app + "-([0-9]|proxy)\" --format {{.Names}}")
        if(len(resp)>0):
            for container in resp:
                print("Deleting app resource " + container)
                resp = stop_delete_container(container)
                if resp != "":
                    print("Success!")
                else:
                    print("Failed!")
        print("Deleting app network " + app + "-net")
        resp = run_docker_command("network rm " + app + "-net")
        if len(resp)>0:
            if resp != "":
                print("Success!")
            else:
                print("Failed!")
        
        # delete record
        print("Deleting app data")
        db_execute("delete from tb_ctn where app_id = '" + str(row[0][0]) + "'")
        db_execute("delete from tb_app where id = '" + str(row[0][0]) + "'")
        print("Success!")
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
            app = row[1]
            print("Application exists, scaling is possible")
            
            old_replicas = db_execute("select count(*) as num from tb_ctn where app_id = '" + str(app_id) + "'")[0][0]
            new_replicas = int(known_args["replicas"])
            
            if(new_replicas > old_replicas):
                print("Performing up scale...")
                
                # update replace var
                update_obj_replace(row[2], row[3])
                
                # create iterable container
                create_iterable_service(app_id, (new_replicas - old_replicas))
                
                # update cfg based on available container
                update_haproxy_cfg(app_id)
                
                docker_compose(yaml_itr, "--no-start", True)
                app_start(True)
                
                #refresh service
                run_docker_command("kill -s HUP " + app + "-proxy")
        
            elif(new_replicas < old_replicas):
                
                print("Performing down scale...")
                
                # update replace var
                update_obj_replace(app, row[2])
                
                # delete first container
                delete_n_first_container(app_id, old_replicas - new_replicas)
                
                # get the rest for updating cfg
                update_haproxy_cfg(app_id)
                
                run_docker_command("kill -s HUP " + app + "-proxy")
                print("App backed server has been down scaled into " + str(new_replicas))
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

def docker_check_image_new(repo):
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
        
        print("Updating application " + app)
        replicas = db_execute("select count(*) as num from tb_ctn where app_id = '" + str(app_id) + "'")[0][0]
        
        # get 25% to down and 50% to add
        num_del = math.floor(replicas*0.25)
        num_add = math.ceil(replicas*0.5)
        
        print("Update strategy will be done half by half. Please wait until finish!")
        
        # get main container image
        dc = replace_variable(tpl_dc)
        ar_dc = dc.split("### ITERABLE CONTAINER BLOCK ###")
        ctn_iterable1 = ar_dc[1].replace("${no}", str(1))
        
        image = search_yaml_value(ctn_iterable1, "image")
        if image!="":
            # check and automatically download image
            if docker_check_image_new(image):
                # if image is new then proceed update
                
                # delete 25% first container
                delete_n_first_container(app_id, num_del)
                
                # create 50% new container
                create_iterable_service(app_id, num_add)
                
                # update cfg based on available container
                update_haproxy_cfg(app_id)
                
                # deploy container & update config
                docker_compose(yaml_itr, "--no-start", True)
                
                # wait until finish and start app
                app_start(True)
                
                #refresh service
                run_docker_command("kill -s HUP " + app + "-proxy")
                
                # once the routine is entering here, it means already running
                # so, delete the first 8 and replace with 5 new
                delete_n_first_container(app_id, replicas-num_del)
                create_iterable_service(app_id, replicas-num_add)
                
                # update cfg based on available container
                update_haproxy_cfg(app_id)
                
                # deploy container & update config
                docker_compose(yaml_itr, "--no-start", True)
                
                # wait until finish and start app
                app_start(True)
                
                #refresh service
                run_docker_command("kill -s HUP " + app + "-proxy")
                
            else:
                print("Image is already up to date. Skipped")
        else:
            print("Image not found in the YAML template file, cannot update")
        
    else:
        info_app_not_found("update")


str_args = " ".join(sys.argv).replace("=", " ")
args1 = str_args.split(" ")
args = []
for arg in args1:
    if arg=='--port': arg = '-p'
    if arg=='--replicas': arg = '-r'
    if arg=='--interactive': arg = '-i'
    if arg=='--start': arg = '-s'
    if arg=='--force-update': arg = '-fu'
    if arg=='--file': arg = '-f'
    args.append(arg)

known_args = {}
known_args["app"] = get_arg_after("-a")
known_args["ports"] = get_arg_after("-p")
known_args["replicas"] = get_arg_after("-r")
known_args["file"] = get_arg_after("-f")

# print(args)

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

if not os.path.exists(tmpdir):
    os.mkdir(tmpdir)        
if not os.path.exists(dir_cfg):
    os.mkdir(dir_cfg)
if not os.path.exists(dir_db):
    os.mkdir(dir_db)

# prepare database
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
    if args[1]=="create":
        app_create(args[2])
    elif args[1]=="start":
        app_start()
    elif args[1]=="stop":
        app_stop()
    elif args[1]=="delete":
        app_delete()
    elif args[1]=="scale":
        app_scale()        
    elif args[1]=="update":
        app_update()   
    else: print(f'''
AMProxy is an easy to use manageable load balancer for multiple docker containers. It utilizes HAProxy inside the lightweight linux alpine distribution docker image.

To start an application, edit the existing docker-compose.yaml template file and run the following command:
{app_name} create app your-app-name -p external_port:internal_port:statistic_port --replicas=number_of_backend_server

Example: {app_name} create app hello-world -p 81:80:82 --replicas=10

Available commands:
create      To create the application, see the above example
start       To start the already created application
stop        To stop currently running application
scale       To scale up / down the running application, example: {app_name} scale hello-world --replicas=20
update      To update container with the newest image, done half by half
delete      To delete the application and all resources


Available parameters:
-p, --port          Ports setting, consists of three ports, external_port:internal_port:statistic_port
                    external_port: externally accessible port for your application service
                    internal_port: internal / service container port (for http usually 80)
                    statistic_por: externally accessible port for load balancer statistic
-r, --replicas      Number of backend server instances
-i, --interactive   Keep STDIN open even if not attached
-s, --start         To directly start application after created
-f, --file [file]   Custom yaml file

Upon started, your application is available at the following URL:
Application service: http://localhost:external_port
Load balancing statistic: http://localhost:statistic_port
''')
else:
    print("No argument supplied")