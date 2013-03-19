#!/usr/bin/python3

__version__ = '0.2'

import sys
import os
import os.path
import subprocess
import time
import socket


class LocalMount:
	def __init__(self, dir, mount_dir):
		self.dir = dir
		self.mount_dir = mount_dir
	#enddef

	def check(self):
		pass
	#enddef

	def mount(self):
		try: os.unlink(self.mount_dir)
		except: pass

		print('symlinking local directory %s' % self.dir)
		os.symlink(self.dir, self.mount_dir)
	#enddef

	def umount(self):
		print('removing symlink for directory %s' % self.dir)
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
		if not self.process: return

		ret = self.process.poll()

		if ret is None: return

		print('return code for %s is %s' % (self.host, ret))

		self.process = None

		self.mount()
	#enddef

	def mount(self):
		print('mounting %s on %s' % (self.host, self.mount_dir))

		subprocess.call('fusermount -u %s' % self.mount_dir, shell=True)

		try: os.mkdir(self.mount_dir)
		except OSError: pass

		cmd = 'sshfs -f -o reconnect,ConnectTimeout=2,CompressionLevel=1,ServerAliveInterval=10 %s %s' % (self.host, self.mount_dir)
		self.process = subprocess.Popen(cmd, shell=True)
	#enddef

	def umount(self):
		if not self.process:
			print ('%s on %s already unmounted' % (self.host, self.mount_dir))
			return
		#endif

		print('unmounting %s from %s' % (self.host, self.mount_dir))
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
		try: os.mkdir('%s/union' % self.mount_dir)
		except OSError: pass

		print('mounting union')
		union_str = ':'.join([i + '=RW' for i in self.branches])
		self.process = subprocess.Popen('unionfs -o relaxed_permissions %s %s/union' % (union_str, self.mount_dir), shell=True)
	#enddef

	def umount(self):
		print('terminating union mount')
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


def main():
	list_fn = sys.argv[1]
	mount_root = sys.argv[2]

	f = open(list_fn, 'r')
	hosts = [i.strip() for i in f.readlines()]
	f.close()

	if not os.path.isdir(mount_root):
		print('%s does not exist, creating it' % mount_root)
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
				m.check()
			#endfor

			time.sleep(1)
		#endwhile
	except KeyboardInterrupt:
		pass
	#endtry

	union.umount()

	for i in mounts:
		m.umount()
	#endfor
#enddef

if __name__ == '__main__':
	main()
#endif
