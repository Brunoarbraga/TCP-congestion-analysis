from __future__ import print_function
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.link import TCLink
from mininet.node import OVSController
import time
import re
import csv


# Parâmetros
#===================================================================
# tamanho do buffer do gargalo
BUFFER_SIZES = [100, 50, 20, 10, 5, 1]
TCP_ALGORITHMS = ['cubic', 'bbr']
IPERF_DURATION = 30
BOTTLENECK_BW = 10
BOTTLENECK_DELAY = '5ms'
H1_DELAY = '25ms'  # fluxo com menor RTT (simula acesso local)
H2_DELAY = '150ms'  # fluxo com maior RTT (simula acesso remoto de outro país)
IPERFS_PER_BUFFER_SIZE = 10
#===================================================================



class NetworkTopology( Topo ):
    # Constrói a topologia da rede
    def build( self, buffer_size=100, **_opts ):
   
        # switchs
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        
        # link gargalo
        self.addLink(s1, s2, cls=TCLink, 
                     bw=BOTTLENECK_BW, 
                     delay=BOTTLENECK_DELAY, 
                     max_queue_size=buffer_size)

        # hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        
        # link com RTT 
        self.addLink(h1, s1, cls=TCLink, delay=H1_DELAY)
        self.addLink(h2, s1, cls=TCLink, delay=H2_DELAY)
        self.addLink(h3, s2)


# muda o algoritmo TCP
def setTcpAlgorith(net, tcp):
    for host in net.hosts:
        host.cmd(f'sysctl -w net.ipv4.tcp_congestion_control={tcp}')



def parse_iperf_throughput(output):
    "Extrai o throughput da saída do cliente (h1 e h2)"
    matches = re.findall(
        r'([\d.]+)\s+(K|M|G)bits/sec',
        output
    )
    if not matches:
        return None
    # Última linha de sumário (iperf -c imprime várias, a última é o total)
    val, unit = matches[-1]
    val = float(val)
    if unit == 'K':
        val /= 1000
    elif unit == 'G':
        val *= 1000
    return round(val, 4)


def runExperiment(buffer_size, tcp):

    info (f'Buffer = {buffer_size} packets | TCP = {tcp}\n')

    topo = NetworkTopology(buffer_size=buffer_size)
    net = Mininet(topo=topo, controller=OVSController, link=TCLink)
    net.start()

    setTcpAlgorith(net, tcp)

    h1 = net.get('h1')
    h2 = net.get('h2')
    h3 = net.get('h3')

    h3_ip = h3.IP()
    info(f' H3 ip = {h3_ip}\n')
    time.sleep(2)

    # inicia servidor h3
    h3.cmd('pkill ´f iperf 2>dev/null; sleep 0.5')
    h3.cmd('iperf -s -D')
    time.sleep(1)

    # iperf de h1 e h2
    info('Começando iperf de h1 e h2')
    h1.cmd(f'iperf -c {h3_ip} -t {IPERF_DURATION} > /tmp/iperf_h1.txt 2>&1 &')
    h2.cmd(f'iperf -c {h3_ip} -t {IPERF_DURATION} > /tmp/iperf_h2.txt 2>&1 &')
    
    # aguarda os processos terminarem
    h1.cmd('wait')
    h2.cmd('wait')


    # coleta de resultado
    out_h1 = h1.cmd('cat /tmp/iperf_h1.txt')
    out_h2 = h2.cmd('cat /tmp/iperf_h2.txt')
    tput_h1 = parse_iperf_throughput(out_h1)
    tput_h2 = parse_iperf_throughput(out_h2)


    info(f' Throughput h1: {tput_h1} Mbps\n')
    info(f' Throughput h2: {tput_h2} Mbps\n')
    # calcular unfairness aqui 

    h3.cmd('pkill -f iperf 2>/dev/null')
    net.stop()

    time.sleep(3) # pausa entre testes

    return tput_h1, tput_h2

def runTests():
    results = []
    with open('results.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            'tcp_algorithm',
            'buffer_size',
            'avg_throughput_h1_mbps',
            'avg_throughput_h2_mbps'
        ])

        for tcp_algorithm in TCP_ALGORITHMS:
            for buffer in BUFFER_SIZES:

                h1_vals = []
                h2_vals = []

                for iterations in range(IPERFS_PER_BUFFER_SIZE): 

                    tput_h1, tput_h2 = runExperiment(buffer, tcp_algorithm)
                    h1_vals.append(tput_h1)
                    h2_vals.append(tput_h2)


                avg_h1 = round((sum(h1_vals) / len(h1_vals)), 4)
                avg_h2 = round((sum(h2_vals) / len(h2_vals)), 4)

                writer.writerow([
                    tcp_algorithm,
                    buffer,
                    avg_h1,
                    avg_h2
                ])

                results.append({
                    'tcp_algorithm' : tcp_algorithm,
                    'buffer_size' : buffer,
                    'throughput_h1(Mbps)' : avg_h1,
                    'throughput_h2(Mbps)' : avg_h2
                })

    return results


if __name__ == '__main__':
    setLogLevel( 'info' )
    results = runTests()

    # todo - mudar para gerar CSV ao invés de txt
    with open('results.txt', 'w') as f:
        f.write(f"{'Algorithm':<12} {'Buffer':>8} {'h1 (Mbps)':>12} {'h2 (Mbps)':>12}\n")
        f.write("-" * 50 + "\n")
        for r in results:
            f.write(f"{r['tcp_algorithm']:<12} {r['buffer_size']:>8} {str(r['throughput_h1(Mbps)']):>12} {str(r['throughput_h2(Mbps)']):>12}\n")
