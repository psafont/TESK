#!/usr/bin/python

from __future__ import print_function
from ftplib import FTP
import ftplib
import argparse
import requests
import sys
import json
import re
import os
import distutils.dir_util

debug = True

def download_ftp_file(source, target, ftp):
  basedir = os.path.dirname(target)
  distutils.dir_util.mkpath(basedir)

  ftp.retrbinary("RETR "+source, open(target, 'w').write)
  return 0

def process_upload_dir(source, target, ftp):
  basename = os.path.basename(source)
  try:
    print('trying to create dir: ' + '/'+target+'/'+basename, file=sys.stderr)
    ftp.mkd('/'+target+'/'+basename)
  except ftplib.error_perm:
    print('Directory exists, overwriting')

  for f in os.listdir(source):
    if os.path.isdir(source+'/'+f):
      process_upload_dir(source+'/'+f, target+'/'+basename+'/', ftp)
    elif os.path.isfile(source+'/'+f):
      ftp.storbinary("STOR "+target+'/'+basename+'/'+f, open(source+'/'+f, 'r'))
  return 0

def process_ftp_dir(source, target, ftp):
  ftp.cwd('/'+source)

  ls = []
  ftp.retrlines('LIST', ls.append)

  # This is horrible and I'm sorry but it works flawlessly. Credit to Chris Haas for writing this
  # see https://stackoverflow.com/questions/966578/parse-response-from-ftp-list-command-syntax-variations for attribution
  p = re.compile('^(?P<dir>[\-ld])(?P<permission>([\-r][\-w][\-xs]){3})\s+(?P<filecode>\d+)\s+(?P<owner>\w+)\s+(?P<group>\w+)\s+(?P<size>\d+)\s+(?P<timestamp>((\w{3})\s+(\d{2})\s+(\d{1,2}):(\d{2}))|((\w{3})\s+(\d{1,2})\s+(\d{4})))\s+(?P<name>.+)$')
  for l in ls:
    dirbit = p.match(l).group('dir')
    name = p.match(l).group('name')

    if dirbit == 'd':
      process_ftp_dir(source+'/'+name, target+'/'+name, ftp)
    else:
      download_ftp_file(name, target+'/'+name, ftp)

def process_ftp_file(ftype, afile):
  p = re.compile('[a-z]+://([-a-z.]+)/(.*)')
  ftp_baseurl = p.match(afile['url']).group(1)
  ftp_path = p.match(afile['url']).group(2)

  ftp = FTP(ftp_baseurl)
  if os.environ.get('TESK_FTP_USERNAME') is not None:
    try:
      user = os.environ['TESK_FTP_USERNAME']
      pw   = os.environ['TESK_FTP_PASSWORD']
      ftp.login(user, pw)
    except ftplib.error_perm:
      ftp.login()
  else:
    ftp.login()

  if ftype == 'inputs':
    if afile['type'] == 'FILE':
      return download_ftp_file(ftp_path, afile['path'], ftp)
    elif afile['type'] == 'DIRECTORY':
      return process_ftp_dir(ftp_path, afile['path'], ftp)
    else:
      print('Unknown file type')
      return 1
  elif ftype == 'outputs':
    if afile['type'] == 'FILE':
      ftp.storbinary("STOR "+ftp_path, open(afile['path'], 'r'))
      return 0
    elif afile['type'] == 'DIRECTORY':
      return process_upload_dir(afile['path'], ftp_path, ftp)
    else:
      print('Unknown file type: '+afile['type'])
      return 1
  else:
    print('Unknown file action: ' + ftype)
    return 1

def process_http_file(ftype, afile):
  if ftype == 'inputs':
    r = requests.get(afile['url'])
    fp = open(afile['path'], 'wb')
    fp.write(r.content)
    fp.close
    return 0
  elif ftype == 'outputs':
    fp = open(afile['path'], 'r')
    r = requests.put(afile['url'], data=fp.read())
    fp.close
    return 0
  else:
    print('Unknown action')
    return 1

def filefromcontent(afile):
  content = afile.get('content')
  if content is None:
    print('Incorrect file spec format, no content or url specified', file=sys.stderr)
    return 1

  fh = open(afile['path'], 'w')
  fh.write(str(afile['content']))
  fh.close()
  return 0

def process_file(ftype, afile):
  url = afile.get('url')

  if url is None:
    return filefromcontent(afile)

  p = re.compile('([a-z]+)://')
  protocol = p.match(url).group(1)
  debug('protocol is: '+protocol)

  if protocol == 'ftp':
    return process_ftp_file(ftype, afile)
  elif protocol == 'http' or protocol == 'https':
    return process_http_file(ftype, afile)
  else:
    print('Unknown file protocol')
    return 1

def debug(msg):
  if debug:
    print(msg, file=sys.stderr)

def main(argv):
  parser = argparse.ArgumentParser(description='Filer script for down- and uploading files')
  parser.add_argument('filetype', help='filetype to handle, either \'inputs\' or \'outputs\' ')
  parser.add_argument('data', help='file description data, see docs for structure')
  args = parser.parse_args()

  data = json.loads(args.data)

  for afile in data[args.filetype]:
    debug('processing file: '+afile['path'])
    if process_file(args.filetype, afile):
      print('something went wrong', file=sys.stderr)
      return 1
    # TODO a bit more detailed reporting
    else:
      debug('Processed file: ' + afile['path'])

  return 0
if __name__ == "__main__":
  main(sys.argv)
