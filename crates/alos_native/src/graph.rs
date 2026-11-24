use petgraph::graph::NodeIndex;
use petgraph::visit::Bfs;
use petgraph::Graph;
use pyo3::prelude::*;
use std::collections::hash_map::Entry;
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
        if let Entry::Vacant(slot) = self.node_map.entry(name) {
            let idx = self.graph.add_node(slot.key().clone());
            slot.insert(idx);
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
            // Nodes past the requested depth never receive a distance; skip them.
            let current_dist = match distances.get(&nx) {
                Some(&dist) => dist,
                None => continue,
            };
            visited.insert(self.graph[nx].clone());

            if current_dist < depth {
                for neighbor in self.graph.neighbors(nx) {
                    distances.entry(neighbor).or_insert(current_dist + 1);
                }
            }
        }

        Ok(visited.into_iter().collect())
    }
}

impl Default for FastGraphEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::FastGraphEngine;
    use proptest::prelude::*;

    #[test]
    fn neighborhood_stops_at_depth_zero_one_and_cycles() {
        let mut engine = FastGraphEngine::default();
        engine.add_node("isolated".to_string());
        engine.add_node("isolated".to_string());
        engine.add_edge("a".to_string(), "b".to_string());
        engine.add_edge("b".to_string(), "c".to_string());
        engine.add_edge("c".to_string(), "a".to_string());
        engine.add_edge("c".to_string(), "d".to_string());

        let d0 = engine.get_neighborhood("a".to_string(), 0).unwrap();
        assert_eq!(d0, vec!["a".to_string()]);

        let mut d1 = engine.get_neighborhood("a".to_string(), 1).unwrap();
        d1.sort();
        assert_eq!(d1, vec!["a".to_string(), "b".to_string(), "c".to_string()]);

        let iso = engine.get_neighborhood("isolated".to_string(), 3).unwrap();
        assert_eq!(iso, vec!["isolated".to_string()]);
    }

    #[test]
    fn unknown_center_returns_only_itself() {
        let engine = FastGraphEngine::new();
        let near = engine.get_neighborhood("missing".to_string(), 2).unwrap();
        assert_eq!(near, vec!["missing".to_string()]);
    }

    proptest! {
        #[test]
        fn graph_neighborhood_monotonic_with_depth(
            edges in prop::collection::vec(("[a-f]", "[a-f]"), 0..20),
            center in "[a-g]",
            depth in 0usize..5,
        ) {
            let mut engine = FastGraphEngine::new();
            for (u, v) in edges {
                engine.add_edge(u, v);
            }
            let n_small = engine.get_neighborhood(center.clone(), depth).unwrap();
            let n_large = engine.get_neighborhood(center.clone(), depth + 1).unwrap();
            prop_assert!(n_small.contains(&center));
            for node in &n_small {
                prop_assert!(n_large.contains(node));
            }
        }
    }
}
