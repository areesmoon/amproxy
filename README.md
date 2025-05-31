# AMProxy

AMProxy is an easy-to-use manageable load balancer for multiple Docker containers. It uses **HAProxy** inside a lightweight Alpine Linux Docker image to provide efficient load balancing across backend services.

---

## Quick Start

To start an application, first edit the provided `docker-compose.yaml.template` file according to your needs, then run:

amproxy create your-app-name -p external_port:internal_port:statistic_port --replicas=number_of_backend_servers

**Example:**

amproxy create hello-world -p 81:80:82 --replicas=10

This command creates an application named `hello-world` with 10 backend instances, forwarding ports accordingly.

---

## Available Commands

| Command   | Description                                                                                                  | Options / Examples                                                   |
|-----------|--------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| create    | Create the application                                                                                        | --image, --replicas, --port, --start                              |
| createdb  | Create application database for an already running AMProxy application                                       | --image, --replicas, --port                                       |
| digest    | Get SHA256 digest from a Docker repository                                                                   | Example: amproxy digest php:alpine                                |
| exec      | Run command inside a worker container or proxy container                                                     | Example: amproxy exec 5 bash (runs bash in container app-name-5)  |
| start     | Start an already created application                                                                         |                                                                    |
| stop      | Stop the currently running application                                                                       |                                                                    |
| scale     | Scale up or down the running application                                                                     | -r / --replicas Example: amproxy scale --replicas=20               |
| update    | Update containers with the newest image, done half-by-half                                                   | -fo / --force, -st / --strategy Example: amproxy update -fo -st 1b1 |
| delete    | Delete an application and all its running containers                                                         |                                                                    |
| reset     | Reset application database (containers must be deleted manually)                                             |                                                                    |
| proc      | Show running instances of backend services                                                                   |                                                                    |
| top       | Show CPU and memory usage of all resources                                                                   |                                                                    |
| docker    | Run any Docker related command (followed by Docker parameters)                                               |                                                                    |
| logs      | Show interactive logs of running containers                                                                  | Options: --proxy, --worker [min:max] Example: amproxy logs --proxy, amproxy logs --worker 2:5 |

---

## Global Parameters

| Flag            | Description                                                                                       |
|-----------------|-------------------------------------------------------------------------------------------------|
| -d, --debug     | Show commands run internally by AMProxy for debugging                                           |
| -f, --file      | Specify a custom YAML file                                                                       |
| -fo, --force    | Force update even if image is not new (used with update command)                                |
| -i, --image     | Specify container Docker image (for direct app creation without using docker-compose template)  |
| -p, --port      | Ports configuration in format external_port:internal_port:statistic_port                         |
|                 | - external_port: externally accessible port for your app service                               |
|                 | - internal_port: internal service/container port (usually 80 for HTTP)                        |
|                 | - statistic_port: externally accessible port for load balancer statistics                      |
| -r, --replicas  | Number of backend server instances                                                              |
| -s, --start     | Start application immediately after creation                                                    |
| -st, --strategy | Update strategy:                                                                               |
|                 | - hbh: half-by-half (default, replace 50% of containers at a time)                            |
|                 | - 1b1: one-by-one (rolling update)                                                          |
| -v, --version   | Show current application version                                                               |

---

## After Starting

Once started, your application is available at:

- Application service: http://localhost:external_port  
- Load balancing statistics: http://localhost:statistic_port

---

## Notes

- Containers use HAProxy inside Alpine Linux for lightweight load balancing.
- Ensure Docker is properly installed and running on your system.
- For detailed usage, use the `--help` option on any command, e.g., `amproxy create --help`.

---

## License

[MIT License](LICENSE)

---