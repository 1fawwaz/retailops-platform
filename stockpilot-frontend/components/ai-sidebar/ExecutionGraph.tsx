"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import type { ExecutionGraphState } from "../../lib/executionGraph";
import { ExecutionGraphNode, type ExecutionGraphNodeData } from "./ExecutionGraphNode";

const NODE_WIDTH = 170;
const NODE_HEIGHT = 54;

const nodeTypes = { agent: ExecutionGraphNode };

function layout(
  graphNodes: ExecutionGraphState["nodes"],
  graphEdges: ExecutionGraphState["edges"],
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 20, ranksep: 48 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const node of graphNodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of graphEdges) {
    g.setEdge(edge.source, edge.target);
  }
  dagre.layout(g);

  const nodesById = new Map(graphNodes.map((node) => [node.id, node]));

  const flowNodes: Node[] = graphNodes.map((node) => {
    const position = g.node(node.id);
    return {
      id: node.id,
      type: "agent",
      position: { x: position.x - NODE_WIDTH / 2, y: position.y - NODE_HEIGHT / 2 },
      data: {
        agentName: node.agentName,
        status: node.status,
        durationMs: node.durationMs,
        toolNames: node.toolNames,
        round: node.round,
      } satisfies ExecutionGraphNodeData,
      draggable: false,
      selectable: false,
    };
  });

  const flowEdges: Edge[] = graphEdges.map((edge) => {
    const sourceNode = nodesById.get(edge.source);
    const superseded = sourceNode?.status === "replanned";
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      animated: sourceNode?.status === "running",
      style: {
        stroke: "var(--color-border-hover)",
        strokeDasharray: superseded ? "4 4" : undefined,
        opacity: superseded ? 0.6 : 1,
      },
    };
  });

  return { nodes: flowNodes, edges: flowEdges };
}

function ExecutionGraphInner({ graph }: { graph: ExecutionGraphState }) {
  const nodeIdKey = graph.nodes.map((n) => n.id).join(",");
  const edgeIdKey = graph.edges.map((e) => e.id).join(",");
  const statusKey = graph.nodes.map((n) => `${n.id}:${n.status}:${n.durationMs}`).join(",");
  const { fitView } = useReactFlow();

  const { nodes, edges } = useMemo(
    () => layout(graph.nodes, graph.edges),
    [nodeIdKey, edgeIdKey, statusKey],
  );

  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 150 });
    });
    return () => cancelAnimationFrame(raf);
  }, [nodeIdKey, edgeIdKey, fitView]);

  useEffect(() => {
    const element = wrapperRef.current;
    if (!element) {
      return;
    }
    const observer = new ResizeObserver(() => {
      fitView({ padding: 0.2, duration: 0 });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [fitView]);

  return (
    <div ref={wrapperRef} className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnScroll
        zoomOnScroll={false}
        minZoom={0.1}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="var(--color-border)" />
      </ReactFlow>
    </div>
  );
}

export function ExecutionGraph({ graph }: { graph: ExecutionGraphState }) {
  return (
    <div className="h-full w-full rounded-md border border-[var(--color-border)] bg-[var(--color-canvas)]">
      <ReactFlowProvider>
        <ExecutionGraphInner graph={graph} />
      </ReactFlowProvider>
    </div>
  );
}
