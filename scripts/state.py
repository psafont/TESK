#!/usr/bin/python

from __future__ import print_function

import argparse
import sys
from kubernetes import client, config

def exec_state(exe_f, namespace, state):

  bv1 = client.BatchV1Api()
  cv1 = client.CoreV1Api()

  with open(exe_f) as exe_fp:
    exe_i = 0
    for exe in exe_fp.readline():
      job = bv1.read_namespaced_job(exe, namespace=namespace)
      state['logs'][exe_i]['start_time'] = job.metadata.creation_timestamp
      state['logs'][exe_i]['end_time'] = job.status.completion_time
      
      job_label_s = 'controller-uid='+job.spec.selector.match_labels['controller-uid']
      pods = cv1.list_namespaced_pod(label_selector=label_s, namespace=namespace)

      try: 
        state['logs'][exe_i]['stdout'] = read_namespaced_pod_log(pods[0].metadata.name, namespace=namespace)
      except IndexError:
        print("No pod matching job "+job.metadata.name+" could be found", file=sys.stderr)

      try:
        state['logs'][exe_i]['exit_code'] = pods[0].status.container_statuses[0].state.terminated.exit_code
      except AttributeError:
        state['logs'][exe_i]['exit_code'] = ''

      exe_i += 1

def tm_state(tm_podname, namespace, state):
  bv1 = client.BatchV1Api()
  cv1 = client.CoreV1Api()

  pods = cv1.list_namespaced_pod(tm_podname, namespace=namespace)
  try: 
    state['system_logs'] = read_namespaced_pod_log(pods[0].metadata.name, namespace=namespace)
  except IndexError:
    print("No pod matching job "+job.metadata.name+" could be found", file=sys.stderr)

  try:
    job_label_s = 'controller-uid='+pods[0].spec.selector.match_labels['controller-uid']
    jobs = bv1.list_namespaced_job(label_selector=job_label_s, namespace=namespace)
    state['start_time'] = jobs[0].metadata.creation_timestamp
    state['end_time'] = jobs[0].status.completion_time
  except IndexError:
    print("Taskmaster job could not be found", file=sys.stderr)

def main(argv):

  state = {}

  parser = argparse.ArgumentParser(description='Taskmaster state script')
  parser.add_argument('exe_f', nargs='?', help='file containing executor job ids', default='/tmp/.exe.tesk')
  parser.add_argument('control_f', nargs='?',  help='file containing taskmaster job id', default='/tmp/.ctl.tesk')
  parser.add_argument('-d', '--debug', help='use local config for debugging', action='store_true')

  args = parser.parse_args()

  if not args.debug:
    config.load_incluster_config()
  else:
    config.load_kube_config()

  exec_state(args.exe_f, 'default', state)
  tm_state(os.environ['KUBE_TASKMASTER_PODNAME'], 'default', state)

  json.dumps(state)
if __name__ == "__main__":
  main(sys.argv)
