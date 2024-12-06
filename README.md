# AMProxy
An Easy Kubernetes-like Load Balancer Proxy

AMProxy is an easy to use manageable load balancer for multiple docker containers. It utilizes HAProxy inside the lightweight linux alpine distribution docker image.


## Creating App
To start an application, edit the existing docker-compose.yaml.template file and run the following command:<br />
`amproxy create your-app-name -p external_port:internal_port:statistic_port --replicas=number_of_backend_server`


## Example
`amproxy create hello-world -p 81:80:82 --replicas=10`


## Available commands:
`create`&emsp;&ensp;Create the application, see the above example<br />
&emsp;&emsp;&emsp; - options: --image, --replicas --port

`createdb`&emsp;Create application database from an already running AMProxy application<br />
&emsp;&emsp;&emsp; - options: --image, --port

`digest`&emsp;&ensp;Get SHA256 digest from a docker repo<br />
&emsp;&emsp;&emsp; Example:<br />
&emsp;&emsp;&emsp; - `amproxy digest php:alpine`

`exec`&emsp;&emsp;Run command inside worker container or proxy container<br />
&emsp;&emsp;&emsp; - option: proxy, worker_no<br />
&emsp;&emsp;&emsp; Example:<br />
&emsp;&emsp;&emsp; - `amproxy exec 5 bash` (this will run bash inside container app-name-5)

`start`&emsp;&ensp; Start the already created application

`stop`&emsp;&emsp;Stop currently running application

`scale`&emsp;&ensp; Scale up / down the running application<br />
&emsp;&emsp;&emsp; - options: -r / --replicas<br />
&emsp;&emsp;&emsp; Example:<br />
&emsp;&emsp;&emsp; - `amproxy scale hello-world --replicas=20`

`update`&emsp;&ensp;Update container with the newest image, done half by half<br />
&emsp;&emsp;&emsp; - options: -fo / --force, -st / --strategy<br />
&emsp;&emsp;&emsp; Example:<br />
&emsp;&emsp;&emsp; - `amproxy update -fo -st 1b1`

`delete`&emsp;&ensp;To delete an application and its all running container

`reset`&emsp;&ensp; Reset application database (containers must be deleted manually)

`proc`&emsp;&emsp;To show running instance of backend service

`top`&emsp;&emsp; To show CPU and memory usage by all resources

`docker`&emsp;&ensp;To run any docker's related command (followed by docker related command's parameters)

`logs`&emsp;&emsp;To see interactive logs of the running containers<br />
&emsp;&emsp;&emsp; - options: --proxy, --worker [worker_no]:[worker_no]<br />
&emsp;&emsp;&emsp; Example:<br />
&emsp;&emsp;&emsp; - `amproxy logs --proxy` (to see proxy logs)<br />
&emsp;&emsp;&emsp; - `amproxy logs --worker 2:5` (to see log worker no 2 to 5)


## Available parameters:
`-d, --debug`&emsp;&emsp; Show command run by AMProxy internal process for debug purpose

`-f, --file [file]`&ensp; Specify custom yaml file

`-fo, --force`&emsp;&emsp;Force update even if the image is not new (used with update)

`-i, --image`&emsp;&emsp; Container's docker image (direct app creation without docker-compose.yaml.template)

`-p, --port`&emsp;&emsp;&ensp;Ports setting, consists of three ports, external_port:internal_port:statistic_port<br />
&emsp;&emsp;&emsp;&emsp;&emsp; - external_port: externally accessible port for your application service<br />
&emsp;&emsp;&emsp;&emsp;&emsp; - internal_port: internal / service container port (for http usually 80)<br />
&emsp;&emsp;&emsp;&emsp;&emsp; - statistic_por: externally accessible port for load balancer statistic

`-r, --replicas`&emsp;&ensp;Number of backend server instances

`-s, --start`&emsp;&emsp; To directly start application after created

`-st, --strategy`&emsp; Update strategy:<br />
&emsp;&emsp;&emsp;&emsp;&emsp; - hbh: half by half (default, container will be replace 50% by 50%)<br />
&emsp;&emsp;&emsp;&emsp;&emsp; - 1b1: one by one (container will be updated 1 by 1)

`-v, --version`&emsp;&ensp; Show current application version

## URL:port
Upon started, your application is available at the following URL:<br />
Application service: http://localhost:external_port<br />
Load balancing statistic: http://localhost:statistic_port