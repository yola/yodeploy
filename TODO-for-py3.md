- [ ] Xenial Jenkins slave (part of https://github.com/yola/production/issues/3687)
  - [ ] chef run fails because:
    - [ ] openrsty?
    - [ ] ???
  - [ ] hookup jenkins slave to master
  - [ ] get jobs on it

  - [ ] apache 2.4 upgrade 

  - [ ] then what? what actually gets it up and running in our stack?
  - [ ] add build jobs to the slave for py3 apps (importer/importservice?)
    - [ ] those apps will need to have build/dist/test scripts set up

- [ ] yodeploy detect python 3 via compat level 5?

build job
deploy job: VVV

yodeploy server-side commands
downloads artifacts
sets up virtualenvs: the deploy requirements, using py3 if needed
  naming the virtualenv appropriately, so it can find it
  whatever looks for this env will need to be updated to handle this
    it's yodeploy on the server that's looking for it
    it currently assumes it's the python it's currently running, we need to change that
runs yodeploy inside the virtualenv to handle the deployments
  hooks, etc. - py3 stuff may break here?
  getting the app's virtualenv setup

- [ ] use the yodeploy in the app's deploy virtualenv to build the virtualenv
  - i'm confused about the details of this step, but could just figure it out by diving in
  - when / where do the yodeploy commands get run? is that the server's or the app's yodeploy doing it?

apache upgrade

postgres dbs

-----

# Yola's Deployment System


