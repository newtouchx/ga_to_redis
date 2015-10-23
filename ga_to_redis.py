import redis
import libvirt
import libvirt_qemu
import time
from bson import ObjectId
import logging
import os
import ConfigParser
import rediscluster


def main():
    logging.basicConfig(format='%(asctime)s.%(msecs)03d %(process)d %(levelname)s [-] %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        filename='/var/log/ga_to_redis.log',
                        filemode='w')
    conn = libvirt.open(None)
    if conn is None:
        logging.error('Failed to open connection to the libvirt')

    ids = conn.listDomainsID()
    if ids is None or len(ids) == 0:
        logging.error('Failed to get running domains')

    cf = ConfigParser.ConfigParser()
    cf.read('/etc/redis_ga.conf')
    redis_ip = cf.get('redis', 'ip')
    redis_port = cf.get('redis', 'port')
    startup_nodes = [{'host': redis_ip, 'port': redis_port}]
    redis_conn = rediscluster.StrictRedisCluster(startup_nodes=startup_nodes, decode_responses=True)

    while True:
        for id in ids:
            dom = conn.lookupByID(id)
            uuid = dom.UUIDString()
            oid = ObjectId()
            try:
                result = libvirt_qemu.qemuAgentCommand(dom, '{"execute":"guest-get-total-info"}', 1, 0)
            except Exception, e:
                if e[0] == 'Guest agent is not responding: QEMU guest agent is not available due to an error':
                    logging.error(e)
                    logging.info('Restarting libvirtd')
                    os.system('systemctl restart libvirtd')
                    conn = libvirt.open(None)
                else:
                    logging.error('instance-%r %r' % (uuid, e))
            else:
                result = eval(result)['return']
                print result
                print oid
                print uuid
                if result != {}:
                    redis_conn.hset('hash_data', oid, result)
                    redis_conn.lpush('list:' + uuid, oid)
        time.sleep(20)

