#!/usr/bin/python

import argparse
import json
import os
import binascii
import re
import time
import sys
from kubernetes import client, config
from datetime import datetime

# translates TES JSON into 1 Job spec per executor
def generate_job_specs(tes):
  exe_i = 0
  specs = []

  for executor in tes['executors']:
    valid_name = tes['name']
    valid_name = valid_name.lower()
    valid_name = re.sub(r" ", "-", valid_name)
    
    specs.append({'apiVersion': 'batch/v1', 'kind': 'Job'})
    specs[exe_i]['metadata'] = {'name': valid_name}

    specs[exe_i]['spec'] = {'template': 0}
    specs[exe_i]['spec']['template'] = { 'metadata' : 0, 'spec': 0}
    
    specs[exe_i]['spec']['template']['metadata'] = {'name': valid_name}

    specs[exe_i]['spec']['template']['spec'] = { 'containers': 0, 'restartPolicy': 'Never'}

    specs[exe_i]['spec']['template']['spec']['containers'] = []

    specs[exe_i]['spec']['template']['spec']['containers'] = []
    specs[exe_i]['spec']['template']['spec']['containers'].append({ 
                                                         'name': valid_name+'-ex'+str(exe_i),
                                                         'image': executor['image'], 
                                                         'command': executor['command'],
                                                         'resources': {'requests': 0 }
                                                        })
    specs[exe_i]['spec']['template']['spec']['containers'][0]['resources']['requests'] = { 
                                                           'cpu': tes['resources']['cpu_cores'], 
                                                           'memory': str(tes['resources']['ram_gb'])+'Gi'}
    
    exe_i += 1
  return specs

def run_executors(specs, polling_interval, namespace, exe_f = '/tmp/.exe.tesk'):

  # init Kubernetes Job API
  v1 = client.BatchV1Api()

  # make sure exe_f is empty
  exe_fp = open(exe_f, 'w')
  exe_fp.close()

  for executor in specs:
    jobname = executor['metadata']['name']+'-'+binascii.hexlify(os.urandom(4))
    executor['metadata']['name'] = jobname
    job = v1.create_namespaced_job(body=executor, namespace=namespace)
    print("Created job with metadata='%s'" % str(job.metadata))
    
    with open(exe_f, 'a') as exe_fp:
      exe_fp.write(jobname+'\n')
      exe_fp.close()
      
    finished = False

    # Job polling loop
    while not finished:
      job = v1.read_namespaced_job(jobname, namespace)
      try:
        #print("job.status.conditions[0].type: %s" % job.status.conditions[0].type)
        if job.status.conditions[0].type == 'Complete' and job.status.conditions[0].status:
          finished = True
        elif job.status.conditions[0].type == 'Failed' and job.status.conditions[0].status:
          finished = True
          return 'Failed' # If an executor failed we break out of running the executors
        else:
          #print("hit else, failing")
          return 'Failed' # something we don't know happened, fail
      except TypeError: # The condition is not initialized, so it is not complete yet, wait for it
        time.sleep(polling_interval)

  return 'Complete' # No failures, so return successful finish

def main(argv):
  parser = argparse.ArgumentParser(description='TaskMaster main module')
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument('json', help='string containing json TES request, required if -f is not given', nargs='?')
  group.add_argument('-f', '--file', help='TES request as a file or \'-\' for stdin, required if json is not given')

  parser.add_argument('-p', '--polling-interval', help='Job polling interval', default=5)
  parser.add_argument('-n', '--namespace', help='Kubernetes namespace to run in', default='default')
  parser.add_argument('-e', '--exec-state', help='Executor state file for state.py script', default='/tmp/.exe.tesk')
  args = parser.parse_args()

  if args.file is None:
    tes = json.loads(args.json)
  elif args.file == '-':
    tes = json.load(sys.stdin)
  else:
    tes = json.load(open(args.file))

  specs = generate_job_specs(tes)

  config.load_incluster_config()

  state = run_executors(specs, args.polling_interval, args.namespace, exe_f=args.exec_state)
  print("Finished with state %s" % state)

if __name__ == "__main__":
  main(sys.argv)
