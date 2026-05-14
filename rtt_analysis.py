#!/usr/bin/python

from __future__ import print_function

import os
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.node import OVSController

# Mudar algoritmo de congestionamento 'bbr' ou 'cubic'
TCP_ALGORITHM = 'cubic'

class NetworkTopology( Topo ):
    # Constrói a topologia da rede
    def build( self, **_opts ):
   
        # switchs
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        
        # link gargalo
        self.addLink(s1, s2, cls=TCLink, bw=10, delay='5ms', max_queue_size=10)

        # hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        
        # link com RTT 
        self.addLink(h1, s1, cls=TCLink, delay='10ms')
        self.addLink(h2, s1, cls=TCLink, delay='50ms')
        self.addLink(h3, s2)

# muda o algoritmo TCP
def setTcpAlgorith(net, tcp):
    info(f'Changing TCP congestion algorithm to {tcp}\n')
    for host in net.hosts:
        host.cmd(f'sysctl -w net.ipv4.tcp_congestion_control={tcp}')
        result = host.cmd('sysctl net.ipv4.tcp_congestion_control')
        info(f'    {host.name}: {result.strip()}\n')


def run():

    topo = NetworkTopology()
    net = Mininet( topo=topo, controller=OVSController, link=TCLink )

    net.start()
    setTcpAlgorith(net, TCP_ALGORITHM)
    CLI( net )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    run()