import logging
import sys

from beiboot.api import create_cluster, remove_cluster, establish_connection

logger = logging.getLogger("getdeck.beiboot")
logger.setLevel("DEBUG")


def create_a_cluster():
    # these are some test ports
    create_cluster(cluster_name=sys.argv[1], ports=["8090:80"])


def connect_a_cluster():
    establish_connection(cluster_name=sys.argv[1])


def remove_a_cluster():
    remove_cluster(cluster_name=sys.argv[1])
