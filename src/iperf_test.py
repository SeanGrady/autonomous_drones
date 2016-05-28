import sys
from subprocess import PIPE, Popen
from threading  import Thread
import time


# Credit to:
# http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x

ON_POSIX = 'posix' in sys.builtin_module_names

def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
        print("mah line " + line)
    out.close()

p = Popen(['iperf','-s','-i','1','-p','5010', '-y', 'c'], stdout=PIPE, bufsize=1, close_fds=ON_POSIX)
q = Queue()
t = Thread(target=enqueue_output, args=(p.stdout, q))
t.daemon = True # thread dies with the program
t.start()

# ... do other things here

# read line without blocking
while True:
    try:
        line = q.get_nowait() # or q.get(timeout=.1)
    except Empty:
        print('no output yet')
    time.sleep(1)
