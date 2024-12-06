# AMProxy
An Easy Kubernetes-like Load Balancer Proxy

AMProxy is an easy to use manageable load balancer for multiple docker containers. It utilizes HAProxy inside the lightweight linux alpine distribution docker image.

## Creating App
To start an application, edit the existing docker-compose.yaml.template file and run the following command:
```
amproxy create your-app-name -p external_port:internal_port:statistic_port --replicas=number_of_backend_server
```

## Example
```
amproxy create hello-world -p 81:80:82 --replicas=10
```

## Available commands:
```
create      Create the application, see the above example
             - options: --image, --replicas --port

createdb    Create application database from an already running AMProxy application
             - options: --image, --port

digest      Get SHA256 digest from a docker repo
             Example:
             - amproxy digest php:alpine

exec        Run command inside worker container or proxy container
             - option: proxy, worker_no
             Example:
             - amproxy exec 5 bash (this will run bash inside container app-name-5)

start       Start the already created application

stop        Stop currently running application

scale       Scale up / down the running application
             - options: -r / --replicas
             Example:
             - amproxy scale hello-world --replicas=20

update      Update container with the newest image, done half by half
             - options: -fo / --force, -st / --strategy
             Example:
             - amproxy update -fo -st 1b1

delete      To delete an application and its all running container

reset       Reset application database (containers must be deleted manually)

proc        To show running instance of backend service

top         To show CPU and memory usage by all resources

docker      To run any docker's related command (followed by docker related command's parameters)

logs        To see interactive logs of the running containers
             - options: --proxy, --worker [worker_no]:[worker_no]
             Example:
             - amproxy logs --proxy (to see proxy logs)
             - amproxy logs --worker 2:5 (to see log worker no 2 to 5)
```

## Available parameters:
```
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
```

## URL:port
Upon started, your application is available at the following URL:<br />
Application service: http://localhost:external_port<br />
Load balancing statistic: http://localhost:statistic_port