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
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        
        # ===== CÁC CẤU TRÚC DỮ LIỆU BẮT BUỘC =====
        self.forwarding_table = {}
        self.distance_vector = {}
        self.neighbor_dv = {}
        self.neighbor_ports = {}

    def _broadcast_dv(self):
        """Gửi distance vector cho tất cả neighbors"""
        # Serialize DV to JSON string (packet content must be string)
        dv_json = json.dumps(self.distance_vector)
        
        for port in self.links.keys():
            packet = Packet(
                kind=Packet.ROUTING,
                src_addr=self.addr,
                dst_addr=None,
                content=dv_json
            )
            self.send(port, packet)

    def _update_routing_table(self):
        """Tính toán DV dựa trên Bellman-Ford"""
        new_dv = {}
        next_hop_map = {}
        
        # Bước 1: Thêm direct neighbors từ links
        for port, link in self.links.items():
            if link.e1 == self.addr:
                neighbor = link.e2
                cost = int(link.l12 / link.latency_multiplier)
            else:
                neighbor = link.e1
                cost = int(link.l21 / link.latency_multiplier)
            
            new_dv[neighbor] = cost
            next_hop_map[neighbor] = neighbor
            self.neighbor_ports[neighbor] = port
        
        # Bước 2: Bellman-Ford - thêm routes qua neighbors
        for neighbor in list(self.neighbor_dv.keys()):
            if neighbor not in new_dv:
                continue
            
            neighbor_cost = new_dv[neighbor]
            neighbor_dv = self.neighbor_dv[neighbor]
            
            for dest, dest_cost in neighbor_dv.items():
                if dest == self.addr:
                    continue
                
                total_cost = neighbor_cost + dest_cost
                
                if dest not in new_dv or total_cost < new_dv[dest]:
                    new_dv[dest] = total_cost
                    next_hop_map[dest] = neighbor
        
        # Bước 3: Tạo forwarding table
        new_ft = {}
        for dest, dist in new_dv.items():
            if dest == self.addr:
                continue
            
            next_hop = next_hop_map.get(dest)
            if next_hop and next_hop in self.neighbor_ports:
                port = self.neighbor_ports[next_hop]
                new_ft[dest] = (port, dist)
        
        self.distance_vector = new_dv
        self.forwarding_table = new_ft

    def handle_packet(self, port, packet):
        """Xử lý packet"""
        
        if packet.is_traceroute:
            # Data packet - lookup FT and forward
            if packet.dst_addr in self.forwarding_table:
                out_port, cost = self.forwarding_table[packet.dst_addr]
                self.send(out_port, packet)
        else:
            # Routing packet - update neighbor DV and recompute
            neighbor_addr = packet.src_addr
            received_dv_json = packet.content
            received_dv = json.loads(received_dv_json)  # Parse JSON string back to dict
            
            # Check if DV changed
            if neighbor_addr not in self.neighbor_dv or self.neighbor_dv[neighbor_addr] != received_dv:
                # Save new DV
                self.neighbor_dv[neighbor_addr] = received_dv
                
                # Recompute routing
                self._update_routing_table()
                
                # Broadcast our DV
                self._broadcast_dv()

    def handle_new_link(self, port, endpoint, cost):
        """Add new link"""
        self._update_routing_table()
        self._broadcast_dv()

    def handle_remove_link(self, port):
        """Remove link"""
        neighbor_to_remove = None
        for neighbor, p in self.neighbor_ports.items():
            if p == port:
                neighbor_to_remove = neighbor
                break
        
        if neighbor_to_remove:
            if neighbor_to_remove in self.neighbor_dv:
                del self.neighbor_dv[neighbor_to_remove]
            if neighbor_to_remove in self.neighbor_ports:
                del self.neighbor_ports[neighbor_to_remove]
        
        self._update_routing_table()
        self._broadcast_dv()

    def handle_time(self, time_ms):
        """Periodic heartbeat"""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast_dv()

    def __repr__(self):
        """Debug info"""
        return (
            f"DV[{self.addr}]\n"
            f"FT: {self.forwarding_table}\n"
            f"DV: {self.distance_vector}"
        )
