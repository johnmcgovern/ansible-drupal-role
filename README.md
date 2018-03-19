# Ansible-Drupal-Role

This is an Ansible role that installs a default Drupal 8 instance and all required configuration and dependancies to support a base Drupal 8 instance. At a high level, this role installs:

- apache2
- php
- mariadb
- composer
- drupal 8
- drush
- drupal 8 modules as specific in group_vars/all

### Setup

1. Copy hosts.sample to hosts
2. Edit hosts file to include desired hosts
3. Copy group_vars/all.sample to group_vars/all
4. Edit group_vars/all variables as appropriate for your enviornment

### Usage
1. Install ansible 
2. Navigate to playbook base directory
3. ansible-playbook -i hosts site.yml
4. ansible-playbook -i hosts --limit=host1 site.yml  #limits to a subset of hosts

### Compatibility

This role is tested on:

- Ubuntu 16.04.4 (LTS)
- Ubuntu 17.10

### ToDo

- Enable php.ini best-practices and tunning for group_vars/all
- Fix password salt randomness generation (currently static)
- Fix the ability to seperate Web and DB server (broken now)

### Contact
- john@johnmcgovern.com
- https://www.johnmcgovern.com
