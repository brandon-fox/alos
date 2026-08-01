use petgraph::graph::NodeIndex;
use petgraph::visit::Bfs;
use petgraph::Graph;
use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};

#[pyclass]
pub struct FastGraphEngine {
    graph: Graph<String, (), petgraph::Undirected>,
    node_map: HashMap<String, NodeIndex>,
}

#[pymethods]
impl FastGraphEngine {
    #[new]
    pub fn new() -> Self {
        FastGraphEngine {
            graph: Graph::new_undirected(),
            node_map: HashMap::new(),
        }
    }

    pub fn add_node(&mut self, name: String) {
        if !self.node_map.contains_key(&name) {
            let idx = self.graph.add_node(name.clone());
            self.node_map.insert(name, idx);
        }
    }

    pub fn add_edge(&mut self, from_node: String, to_node: String) {
        self.add_node(from_node.clone());
        self.add_node(to_node.clone());

        let from_idx = self.node_map[&from_node];
        let to_idx = self.node_map[&to_node];
        self.graph.add_edge(from_idx, to_idx, ());
    }

    pub fn get_neighborhood(&self, center_note: String, depth: usize) -> PyResult<Vec<String>> {
        let center_idx = match self.node_map.get(&center_note) {
            Some(&idx) => idx,
            None => return Ok(vec![center_note]),
        };

        let mut visited = HashSet::new();
        let mut distances: HashMap<NodeIndex, usize> = HashMap::new();
        distances.insert(center_idx, 0);

        let mut bfs = Bfs::new(&self.graph, center_idx);
        while let Some(nx) = bfs.next(&self.graph) {
            let current_dist = distances[&nx];
            if current_dist > depth {
                continue;
            }
            visited.insert(self.graph[nx].clone());

            if current_dist < depth {
                for neighbor in self.graph.neighbors(nx) {
                    if !distances.contains_key(&neighbor) {
                        distances.insert(neighbor, current_dist + 1);
                    }
                }
            }
        }

        Ok(visited.into_iter().collect())
    }
}
