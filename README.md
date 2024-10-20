# amproxy
An Easy Kubernetes-like Load Balancer Proxy

AMProxy is an easy to use manageable load balancer for multiple docker containers. It utilizes HAProxy inside the lightweight linux alpine distribution docker image.

## Creating App
To start an application, edit the existing docker-compose.yaml template file and run the following command:

amproxy create app your-app-name -p external_port:internal_port:statistic_port --replicas=number_of_backend_server

### Example
amproxy create app hello-world -p 81:80:82 --replicas=10

## Available commands:
create      To create the application, see the above example

start       To start the already created application

stop        To stop currently running application

scale       To scale up / down the running application, example: amproxy scale hello-world --replicas=20

update      To update container with the newest image, done half by half

delete      To delete the application and all resources


## Available parameters:
-p, --port          Ports setting, consists of three ports, external_port:internal_port:statistic_port

                    external_port: externally accessible port for your application service

                    internal_port: internal / service container port (for http usually 80)

                    statistic_por: externally accessible port for load balancer statistic

-r, --replicas      Number of backend server instances

-i, --interactive   Keep STDIN open even if not attached

-s, --start         To directly start application after created

-f, --file [file]   Custom yaml file

## URL:port
Upon started, your application is available at the following URL:

Application service: http://localhost:external_port

Load balancing statistic: http://localhost:statistic_port