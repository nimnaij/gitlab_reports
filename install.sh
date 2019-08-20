#!/bin/bash

export ENV_NAME="gitlabenv"

#install pip3
test -z "$(dpkg -l | egrep "python3-dev")" && sudo apt-get install python3-dev 
test -z "$(dpkg -l | egrep "python3-pip")" && sudo apt-get install python3-pip
#install virtualenv
python3 -m pip install --user virtualenv

#create virtualenv called stacksdkenv
if [ ! -e ./${ENV_NAME} ] ; then
  python3 -m virtualenv ${ENV_NAME}
fi
#activate env
. ./${ENV_NAME}/bin/activate

echo [+] confirm env:
if [ -z "$(which python3|grep ${ENV_NAME})" ]; then
  echo [!] env setup failed!
  exit 1
fi


pip3 install python-gitlab 
echo [+] install complete. Drop into env? [y/n]
read garbage
if [ ! "$garbage" == "n" ] ; then
  bash -i
else
  echo OK. You can activate env with:  
  echo . ./${ENV_NAME}/bin/activate
fi
