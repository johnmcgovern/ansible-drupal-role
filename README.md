# Ansible-Drupal-Role

This is an Ansible role that installs a default Drupal instance (latest stable release) with all required configuration and dependancies. At a high level, this role installs:

- apache2 or nginx
- php
- mariadb
- composer
- drush
- drupal (latest stable verison)
- drupal modules as specified in group_vars/all


### Setup

1. Install ansible:
 
		- sudo apt-get install ansible (Ubuntu) 
		- brew install ansible (macOS)

2. git clone this project

		- git clone https://github.com/johnmcgovern/ansible-drupal-role.git	
	
3. Navigate to project base directory

		- cd ./ansible-drupal-role		

4. Copy hosts.sample to hosts

		- cp hosts.sample hosts

5. Edit hosts file to include desired hosts

		- vi hosts
	
6. Copy group_vars/all.sample to group_vars/all

		- cp group_vars/all.sample group_vars/all

7. Edit group_vars/all variables as appropriate for your enviornment

		- vi group_vars/all


### Usage

1. Ensure that python3 is installed on the targer server(s)

		- sudo apt-get install python3
	
2. Navigate to playbook base directory

		- cd ./ansible-drupal-role
	
3. Run the ansible playbook:

		- ansible-playbook -i hosts site.yml
	
4. Run the ansible playbook limited to certain hosts:

		- ansible-playbook -i hosts --limit=host1 site.yml  #limits to a subset of hosts


### Requirements

1. The Ubuntu target server must already have python installed (Ansible needs it to operate):

		- sudo apt-get install python


### Compatibility

This role is tested on:

- Ubuntu 20.04 Server (LTS)

Ubuntu 20.04 contains a modern version of PHP by default (PHP 7.4.x). Drupal 9 and on requires at least PHP 7.3. Therefore I have not attempted to support backwards compatibility of Ubuntu versions as I have in previous versions. I hope to have more time to expand compatibility to CentOS 8 in the future. 


### Notes

- The goal of this role is to perform an installation of base Drupal (latest version) with all dependancies (Nginx/Apache, PHP, MariaDB, permissions, etc.) with no status page errors / issues.
- trusted_host_patterns is not enabled by default but can be easily in group_vars/all. The reason for this is that if it is enabled, but not configured exactly correctly, the site will not be displayed.

### ToDo

- Enable php.ini best-practices and tunning for group_vars/all
- Fix hash salt randomness generation (currently static)
- Fix the ability to seperate Web and DB server (currently broken)


### Contact

- john@johnmcgovern.com
- https://www.johnmcgovern.com

