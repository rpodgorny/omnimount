#!/usr/bin/python3

'''
Usage:
  omnimount [options] <mount_point>

Arguments:
  <mount_point>  Mount point.

Options:
  --list=<list>  Filename of remote host list. [default: list.txt]
'''

__version__ = '0.2'

import sys
import os
import os.path
import subprocess
import time
import socket
import docopt
import logging


class LocalMount:
	def __init__(self, dir, mount_dir):
		self.dir = dir
		self.mount_dir = mount_dir
	#enddef

	def check(self):
		return True
	#enddef

	def mount(self):
		# TODO: do some checking and remove this try/except shit
		try:
			os.unlink(self.mount_dir)
		except:
			pass
		#endtry

		logging.info('symlinking local directory %s' % self.dir)
		os.symlink(self.dir, self.mount_dir)
	#enddef

	def umount(self):
		logging.info('removing symlink for directory %s' % self.dir)
		os.unlink(self.mount_dir)
	#enddef
#endclass


class RemoteMount:
	def __init__(self, host, mount_dir):
		self.host = host
		self.mount_dir = mount_dir
		self.process = None
	#enddef

	def check(self):
		if not self.process: return False

		ret = self.process.poll()

		if ret is None: return True

		logging.debug('return code for %s is %s' % (self.host, ret))

		self.process = None

		return False
	#enddef

	def mount(self):
		logging.info('mounting %s on %s' % (self.host, self.mount_dir))

		subprocess.call('fusermount -u %s' % self.mount_dir, shell=True)

		# TODO: actually check for existence and don't do this try/except shit
		try:
			os.mkdir(self.mount_dir)
		except OSError:
			pass
		#endtry

		cmd = 'sshfs -f -o reconnect,ConnectTimeout=2,CompressionLevel=1,ServerAliveInterval=10 %s %s' % (self.host, self.mount_dir)
		self.process = subprocess.Popen(cmd, shell=True)
	#enddef

	def umount(self):
		if not self.process:
			print ('%s on %s already unmounted' % (self.host, self.mount_dir))
			return
		#endif

		logging.info('unmounting %s from %s' % (self.host, self.mount_dir))
		self.process.terminate()
		self.process.wait()
		self.process = None
	#enddef
#endclass


class UnionMount:
	def __init__(self, mount_dir, branches):
		self.mount_dir = mount_dir
		self.branches = branches
		self.process = None
	#enddef

	def mount(self):
		# TODO: actually check for existence and don't do this try/except shit
		try:
			os.mkdir('%s/union' % self.mount_dir)
		except OSError:
			pass
		#endtry

		logging.info('mounting union')
		union_str = ':'.join([i + '=RW' for i in self.branches])
		self.process = subprocess.Popen('unionfs -o relaxed_permissions %s %s/union' % (union_str, self.mount_dir), shell=True)
	#enddef

	def umount(self):
		logging.info('terminating union mount')
		self.process.terminate()
		self.process.wait()
		self.process = None

		# TODO: the above does not seem to work so call explicit unmount
		subprocess.call('fusermount -u %s/union' % self.mount_dir, shell=True)
	#enddef
#endclass


def is_local(host):
	if socket.gethostname() in host: return True

	return False
#enddef


def logging_setup(level):
	logging.basicConfig(level=level)
#enddef


def main():
	args = docopt.docopt(__doc__, version=__version__)

	logging_setup('DEBUG')

	list_fn = args['--list'] 
	mount_root = args['<mount_point>']

	f = open(list_fn, 'r')
	hosts = [i.strip() for i in f.readlines()]
	f.close()

	if not os.path.isdir(mount_root):
		logging.info('%s does not exist, creating it' % mount_root)
		os.mkdir(mount_root)
	#endif

	mounts = []

	for host in hosts:
		if host.startswith('#'): continue

		mount_path = '%s/%s' % (mount_root, host.replace(':', '--').replace('/', '-'))

		if is_local(host):
			_, local_dir = host.split(':', 1)
			if not local_dir.startswith('/'): local_dir = os.path.expanduser('~/%s' % local_dir)

			m = LocalMount(local_dir, mount_path)
		else:
			m = RemoteMount(host, mount_path)
		#endif

		m.mount()
		mounts.append(m)
	#endfor

	union = UnionMount(mount_root, [i.mount_dir for i in mounts])
	union.mount()

	try:
		while 1:
			for i in mounts:
				if not m.check():
					m.mount()
				#endif
			#endfor

			time.sleep(1)  # TODO: hard-coded shit
		#endwhile
	except KeyboardInterrupt:
		pass
	#endtry

	union.umount()

	for m in mounts:
		m.umount()
	#endfor
#enddef


if __name__ == '__main__':
	main()
#endif
