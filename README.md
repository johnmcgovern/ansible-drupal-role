# Ansible-Drupal-Role

This is an Ansible role that installs a default Drupal 8 instance and all required dependencies.

### Setup

1. Copy hosts.sample to hosts
2. Edit hosts file to include desired hosts
3. Copy group_vars/all.sample
4. Edit group_vars/all variables as appropriate for your enviornment

### Usage
1. Install ansible 
2. Navigate to playbook base directory
3. ansible-playbook -i hosts site.yml

### Compatibility

This role is tested on:

- Ubuntu 16.04.4 (LTS)
- Ubuntu 17.10

### Contact
- john@johnmcgovern.com
- https://www.johnmcgovern.com
