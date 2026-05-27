####################################################
# DVrouter.py
# Name:
# HUID:
#####################################################

from router import Router
from packet import Packet
import sys
import json


class DVrouter(Router):
    """Distance vector routing protocol implementation."""

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.forwarding_table = {}
        self.distance_vector = {}
        self.neighbor_dv = {}
        self.neighbor_ports = {}

    def _broadcast_dv(self):
        dv_json = json.dumps(self.distance_vector)
        for port in self.links.keys():
            packet = Packet(Packet.ROUTING, self.addr, None, dv_json)
            self.send(port, packet)

    def _update_routing_table(self):
        new_dv = {}
        next_hop = {}
        
        # Bước 1: Thêm direct neighbors
        for port, link in self.links.items():
            if link.e1 == self.addr:
                neighbor = link.e2
                cost = int(link.l12 / link.latency_multiplier)
            else:
                neighbor = link.e1
                cost = int(link.l21 / link.latency_multiplier)
            
            new_dv[neighbor] = cost
            next_hop[neighbor] = neighbor
            self.neighbor_ports[neighbor] = port
        
        # Bước 2: Bellman-Ford - tính routes qua neighbors
        for neighbor in self.neighbor_dv.keys():
            if neighbor not in new_dv:
                continue
            
            neighbor_dv = self.neighbor_dv[neighbor]
            neighbor_cost = new_dv[neighbor]
            
            for dest, dest_cost in neighbor_dv.items():
                if dest == self.addr:
                    continue
                
                total_cost = neighbor_cost + dest_cost
                
                if dest not in new_dv or total_cost < new_dv[dest]:
                    new_dv[dest] = total_cost
                    next_hop[dest] = neighbor
        
        # Bước 3: Xây dựng forwarding table
        self.distance_vector = new_dv
        self.forwarding_table = {}
        for dest, dist in new_dv.items():
            if dest == self.addr:
                continue
            
            nh = next_hop.get(dest)
            if nh in self.neighbor_ports:
                port = self.neighbor_ports[nh]
                self.forwarding_table[dest] = (port, dist)

    def handle_packet(self, port, packet):
        if packet.is_traceroute:
            if packet.dst_addr in self.forwarding_table:
                out_port, cost = self.forwarding_table[packet.dst_addr]
                self.send(out_port, packet)
        else:
            neighbor = packet.src_addr
            received_dv = json.loads(packet.content)
            if neighbor not in self.neighbor_dv or self.neighbor_dv[neighbor] != received_dv:
                self.neighbor_dv[neighbor] = received_dv
                self._update_routing_table()
                self._broadcast_dv()

    def handle_new_link(self, port, endpoint, cost):
        self._update_routing_table()
        self._broadcast_dv()

    def handle_remove_link(self, port):
        for neighbor, p in list(self.neighbor_ports.items()):
            if p == port:
                del self.neighbor_ports[neighbor]
                if neighbor in self.neighbor_dv:
                    del self.neighbor_dv[neighbor]
                break
        self._update_routing_table()
        self._broadcast_dv()

    def handle_time(self, time_ms):
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast_dv()

    def __repr__(self):
        return f"DV[{self.addr}] FT:{self.forwarding_table}"
