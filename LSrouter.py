####################################################
# LSrouter.py
# Name:
# HUID:
#####################################################

from router import Router


class LSrouter(Router):
    """Link state routing protocol implementation.

    Add your own class fields and initialization code (e.g. to create forwarding table
    data structures). See the `Router` base class for docstrings of the methods to
    override.
    """

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)
        self.heartbeat_time = heartbeat_time
        self.last_time = 0
        self.forwarding_table = {}
        self.link_state = {}
        self.sequence_num = 0
        self.received_seq = {}
        self.neighbor_ports = {}

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            if packet.dst_addr in self.forwarding_table:
                out_port, cost = self.forwarding_table[packet.dst_addr]
                self.send(out_port, packet)
        else:
            import json
            src, seq_num, received_ls = json.loads(packet.content)
            if src not in self.received_seq or seq_num > self.received_seq[src]:
                self.received_seq[src] = seq_num
                self.link_state[src] = received_ls
                self._update_routing_table()
                for other_port in self.links.keys():
                    if other_port != port:
                        self.send(other_port, packet)

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        if self.addr not in self.link_state:
            self.link_state[self.addr] = {}
        
        # Calculate actual cost from link object
        link = self.links[port]
        if link.e1 == self.addr:
            actual_cost = int(link.l12 / link.latency_multiplier)
        else:
            actual_cost = int(link.l21 / link.latency_multiplier)
        
        self.link_state[self.addr][endpoint] = actual_cost
        self.neighbor_ports[endpoint] = port
        self._update_routing_table()
        self.sequence_num += 1
        self._broadcast_ls()

    def handle_remove_link(self, port):
        """Handle removed link."""
        endpoint = None
        for ep, p in self.neighbor_ports.items():
            if p == port:
                endpoint = ep
                break
        if endpoint:
            if self.addr in self.link_state and endpoint in self.link_state[self.addr]:
                del self.link_state[self.addr][endpoint]
            del self.neighbor_ports[endpoint]
        self._update_routing_table()
        self.sequence_num += 1
        self._broadcast_ls()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast_ls()

    def _dijkstra(self):
        """Dijkstra's algorithm to find shortest paths."""
        import heapq
        
        # Build current local links from actual link objects
        local_links = {}
        for port, link in self.links.items():
            if link.e1 == self.addr:
                neighbor = link.e2
                cost = int(link.l12 / link.latency_multiplier)
            else:
                neighbor = link.e1
                cost = int(link.l21 / link.latency_multiplier)
            local_links[neighbor] = cost
        
        # Build topology: always prefer actual links over old link_state
        topology = {}
        
        # First, add all known link states
        for node, neighbors in self.link_state.items():
            if node not in topology:
                topology[node] = {}
            for neighbor, cost in neighbors.items():
                topology[node][neighbor] = cost
        
        # Then override with our actual current links (this router)
        if self.addr not in topology:
            topology[self.addr] = {}
        topology[self.addr].clear()
        topology[self.addr].update(local_links)
        
        # Dijkstra initialization
        dist = {self.addr: 0}
        parent = {}
        visited = set()
        pq = [(0, self.addr)]
        
        # Dijkstra loop
        while pq:
            cost, node = heapq.heappop(pq)
            if node in visited:
                continue
            visited.add(node)
            
            # Skip if node not in topology
            if node not in topology:
                continue
            
            # Relax edges for all neighbors
            for neighbor, edge_cost in topology[node].items():
                new_cost = cost + edge_cost
                if neighbor not in dist or new_cost < dist[neighbor]:
                    dist[neighbor] = new_cost
                    parent[neighbor] = node
                    heapq.heappush(pq, (new_cost, neighbor))
        
        return dist, parent

    def _update_routing_table(self):
        """Update forwarding table based on Dijkstra."""
        dist, parent = self._dijkstra()
        self.forwarding_table = {}
        
        for dest in dist.keys():
            if dest == self.addr:
                continue
            
            # Tìm next hop: đi ngược từ dest về đến khi gặp neighbor trực tiếp
            node = dest
            while node in parent and parent[node] != self.addr:
                node = parent[node]
            
            # node bây giờ là neighbor trực tiếp
            if node in self.neighbor_ports:
                port = self.neighbor_ports[node]
                self.forwarding_table[dest] = (port, dist[dest])

    def _broadcast_ls(self):
        """Broadcast this router's link state."""
        from packet import Packet
        import json
        
        # Ensure link_state is up-to-date with actual links
        if self.addr not in self.link_state:
            self.link_state[self.addr] = {}
        
        for port, link in self.links.items():
            if link.e1 == self.addr:
                neighbor = link.e2
                actual_cost = int(link.l12 / link.latency_multiplier)
            else:
                neighbor = link.e1
                actual_cost = int(link.l21 / link.latency_multiplier)
            
            self.link_state[self.addr][neighbor] = actual_cost
        
        content = json.dumps((self.addr, self.sequence_num, self.link_state.get(self.addr, {})))
        for port in self.links.keys():
            self.send(port, Packet(Packet.ROUTING, self.addr, None, content))

    def __repr__(self):
        """Debug representation."""
        return f"LS[{self.addr}] FT:{self.forwarding_table}"
