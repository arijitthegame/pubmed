import torch
import torch.nn as nn
import torch.nn.functional as F
from dgl import DGLGraph
import networkx as nx

class GATLayer(nn.module):
	def __init__(self, g, in_dim, out_dim):
		super(GATLayer, self).__init__()
		self.g = g
		self.fc = nn.Linear(in_dim, out_dim, bias=False)
		self.attn_fc = nn.Linear(2*out_dim,1, bias=False)

	def edge_attention(self, edges):
		z2 = torch.cat([edges.src['z'], edges.dst['z']], dim=1)
		a = self.attn_fc(z2)
		return {'e': F.leaky_relu(a)}

	def message_func(self,edges):
		return {'z': edges.src['z'], 'e':edges.data['e']}

	def reduce_func(self, nodes):
		alpha = F.softmax(nodes.mailbox['e'], dim=1)
		h = torch.sum(alpha*nodes.mailbox['z'], dim=1)
		return {'h': h}

	def forward(self, h):
		z = self.fc(h)
		self.g.ndata['z'] = z
		self.g.apply_edges(self.edge_attention)
		self.g.update_all(self.message_func, self.reduce_func)
		return self.g.ndata.pop('h')

class MultiHeadGATLayer(nn.module):
	def __init__(self, g, in_dim, out_dim, num_heads, merge='cat'):
		super(MultiHeadGATLayer, self).__init__()
		self.heads = nn.ModuleList()
		for i in range(num_heads):
			self.heads.append(GATLayer(g, in_dim, out_dim))
		self.merge = merge

	def forward(self, h):
		head_outs = [attn_head(h) for attn_head in self.heads]
		if self.merge == 'cat':
			return torch.cat(head_outs, dim=1)
		else: 
			return torch.mean(torch.stack(head_outs))

class GAT(nn.Module):
	def __init__(self, g, in_dim, hidden_dim0, hidden_dim1, hidden_dim2, out_dim, num_heads):
		super(GAT, self).__init__()
#Pick the number of layers you want. This is a simple 4 layer GAT
		self.layer1 = MultiHeadGATLayer(g, in_dim, hidden_dim0, num_heads)
		self.layer2 = MultiHeadGATLayer(g, hidden_dim0*num_heads, hidden_dim1, num_heads)
		self.layer3 = MultiHeadGATLayer(g, hidden_dim1*num_heads, hidden_dim2, num_heads)
		self.layer4 = MultiHeadGATLayer(g, hidden_dim2*num_heads, output_dim, 1) 

	def forward(self, h):
		h = self.layer1(h)
		h = F.elu(h)
		h = self.layer2(h)
		h = F.elu(h)
		h = self.layer3(h)
		h = F.elu(h)
		h = self.layer4(h)
		return h
