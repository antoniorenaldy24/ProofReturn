"use client";

import { useMemo, useRef } from "react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, Float, OrbitControls } from "@react-three/drei";
import { HERO_HOTSPOTS } from "@/lib/data";

/* ————————————————————————————————————————————————
   RETURN LAB — optical bay.
   The specimen is built entirely from primitives so the demo
   stays dependency-light: torus headband, cylinder cups,
   emissive scan rings. Drag to orbit, toggle to explode.
   Hotspot DOM markers are projected imperatively (no portals).
———————————————————————————————————————————————— */

const SHELL = { color: "#23272c", metalness: 0.55, roughness: 0.42 };
const DARK = { color: "#14171b", metalness: 0.2, roughness: 0.85 };
const PLATE = { color: "#383e46", metalness: 0.8, roughness: 0.3 };

export type AnchorRegistry = Record<string, THREE.Object3D | null>;
export type NodeRegistry = Record<string, HTMLElement | null>;

function useDamped(target: number, stiffness = 5) {
  const cur = useRef(target);
  useFrame((_, delta) => {
    cur.current = THREE.MathUtils.damp(cur.current, target, stiffness, delta);
  });
  return cur;
}

function setAnchor(
  anchors: React.RefObject<AnchorRegistry>,
  id: string,
): (obj: THREE.Object3D | null) => void {
  return (obj) => {
    anchors.current[id] = obj;
  };
}

function ScanRing({ paused }: { paused: boolean }) {
  const ring = useRef<THREE.Mesh>(null);
  const progress = useRef(0);
  useFrame((state, delta) => {
    if (!ring.current) return;
    const m = ring.current.material as THREE.MeshBasicMaterial;
    if (paused) {
      ring.current.position.y = 0.35;
      m.opacity = 0.25;
      return;
    }
    progress.current = (progress.current + delta * 0.22) % 1;
    const p = progress.current;
    ring.current.position.y = -1.55 + p * 3.3;
    m.opacity = Math.sin(Math.PI * p) * 0.8;
    const s = 1 + Math.sin(state.clock.elapsedTime * 9) * 0.004;
    ring.current.scale.setScalar(s);
  });
  return (
    <mesh ref={ring} rotation={[Math.PI / 2, 0, 0]} position={[0, -1.55, 0]}>
      <torusGeometry args={[2.1, 0.008, 8, 96]} />
      <meshBasicMaterial color="#d63a00" transparent opacity={0} />
    </mesh>
  );
}

function Cup({
  side,
  explodeCur,
  ids,
  anchors,
  selectedId,
}: {
  side: 1 | -1;
  explodeCur: React.RefObject<number>;
  ids: string[];
  anchors: React.RefObject<AnchorRegistry>;
  selectedId: string | null;
}) {
  const group = useRef<THREE.Group>(null);
  const face = useRef<THREE.Group>(null);
  const ringMat = useRef<THREE.MeshStandardMaterial>(null);
  const dotMat = useRef<THREE.MeshStandardMaterial>(null);
  const baseX = side * 1.05;

  useFrame(({ clock }) => {
    const e = explodeCur.current ?? 0;
    if (group.current) group.current.position.x = baseX + e * side * 0.55;
    if (face.current) face.current.position.x = e * side * 0.3;
    const t = clock.elapsedTime;
    const active =
      selectedId === (side === 1 ? "c4" : "c3") || selectedId === "c7";
    if (ringMat.current)
      ringMat.current.emissiveIntensity =
        1.2 + Math.sin(t * 3) * 0.45 + (active ? 1.6 : 0);
    if (dotMat.current)
      dotMat.current.emissiveIntensity = 0.9 + Math.sin(t * 2.2) * 0.35;
  });

  return (
    <group ref={group} position={[baseX, -0.35, 0]}>
      {/* shell */}
      <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.58, 0.58, 0.26, 48]} />
        <meshStandardMaterial {...SHELL} />
      </mesh>
      {/* hinge stub */}
      <mesh position={[0, 0.52, 0]}>
        <cylinderGeometry args={[0.055, 0.055, 0.16, 16]} />
        <meshStandardMaterial {...PLATE} />
      </mesh>
      {/* movable face: plate + accent ring + cushion + driver dot */}
      <group ref={face}>
        <mesh position={[side * 0.15, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.42, 0.42, 0.02, 48]} />
          <meshStandardMaterial {...PLATE} />
        </mesh>
        <mesh position={[side * 0.14, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
          <torusGeometry args={[0.5, 0.012, 8, 72]} />
          <meshStandardMaterial
            ref={ringMat}
            color="#d63a00"
            emissive="#d63a00"
            emissiveIntensity={1.1}
            metalness={0.4}
            roughness={0.3}
          />
        </mesh>
        <mesh position={[-side * 0.17, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
          <torusGeometry args={[0.37, 0.125, 16, 48]} />
          <meshStandardMaterial {...DARK} />
        </mesh>
        <mesh position={[-side * 0.185, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.09, 0.09, 0.02, 24]} />
          <meshStandardMaterial
            ref={dotMat}
            color="#2eb567"
            emissive="#2eb567"
            emissiveIntensity={0.9}
          />
        </mesh>
      </group>
      {/* controls on right plate / mic stub on left */}
      {side === 1 ? (
        <group position={[side * 0.165, 0, 0]}>
          <mesh position={[0, 0.2, 0.14]}>
            <boxGeometry args={[0.02, 0.06, 0.06]} />
            <meshStandardMaterial color="#454c55" metalness={0.6} roughness={0.4} />
          </mesh>
          <mesh position={[0, 0.1, 0.14]}>
            <boxGeometry args={[0.02, 0.06, 0.06]} />
            <meshStandardMaterial color="#454c55" metalness={0.6} roughness={0.4} />
          </mesh>
        </group>
      ) : (
        <mesh position={[0, -0.66, 0.12]}>
          <cylinderGeometry args={[0.018, 0.018, 0.18, 12]} />
          <meshStandardMaterial {...PLATE} />
        </mesh>
      )}
      {/* anchor points ride with the cup */}
      {ids.map((id) => {
        const h = HERO_HOTSPOTS.find((x) => x.id === id);
        if (!h) return null;
        return (
          <object3D
            key={id}
            ref={setAnchor(anchors, id)}
            position={h.pos}
          />
        );
      })}
    </group>
  );
}

function Headset({
  explodeCur,
  anchors,
  selectedId,
}: {
  explodeCur: React.RefObject<number>;
  anchors: React.RefObject<AnchorRegistry>;
  selectedId: string | null;
}) {
  const band = useRef<THREE.Group>(null);
  useFrame(() => {
    const e = explodeCur.current ?? 0;
    if (band.current) band.current.position.y = 0.3 + e * 0.38;
  });

  const bandAnchor = HERO_HOTSPOTS.find((h) => h.id === "c1");

  return (
    <group>
      {/* headband */}
      <group ref={band} position={[0, 0.3, 0]}>
        <mesh castShadow>
          <torusGeometry args={[1.35, 0.085, 16, 72, Math.PI]} />
          <meshStandardMaterial {...SHELL} />
        </mesh>
        <mesh position={[0, -0.05, 0]}>
          <torusGeometry args={[1.27, 0.045, 12, 64, Math.PI * 0.92]} />
          <meshStandardMaterial {...DARK} />
        </mesh>
        {bandAnchor ? (
          <object3D
            ref={setAnchor(anchors, bandAnchor.id)}
            position={bandAnchor.pos}
          />
        ) : null}
      </group>

      {/* sliders */}
      {[1, -1].map((side) => {
        const s = side as 1 | -1;
        return (
          <mesh
            key={s}
            position={[s * 1.2, -0.02, 0]}
            rotation={[0, 0, -s * 0.432]}
            castShadow
          >
            <cylinderGeometry args={[0.045, 0.045, 0.74, 16]} />
            <meshStandardMaterial {...PLATE} />
          </mesh>
        );
      })}

      <Cup
        side={-1}
        explodeCur={explodeCur}
        ids={["c3", "c5"]}
        anchors={anchors}
        selectedId={selectedId}
      />
      <Cup
        side={1}
        explodeCur={explodeCur}
        ids={["c4", "c7"]}
        anchors={anchors}
        selectedId={selectedId}
      />
    </group>
  );
}

function StageRig() {
  const ticks = useMemo(
    () => Array.from({ length: 12 }, (_, i) => (i / 12) * Math.PI * 2),
    [],
  );
  return (
    <group position={[0, -1.58, 0]}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.05, 0.006, 6, 96]} />
        <meshBasicMaterial color="#c9cdc3" />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.55, 0.004, 6, 96]} />
        <meshBasicMaterial color="#e0e2da" />
      </mesh>
      {ticks.map((a, i) => (
        <mesh
          key={i}
          position={[Math.cos(a) * 2.05, 0, Math.sin(a) * 2.05]}
          rotation={[0, -a, 0]}
        >
          <boxGeometry args={[0.09, 0.004, 0.02]} />
          <meshBasicMaterial color={i % 3 === 0 ? "#d63a00" : "#c9cdc3"} />
        </mesh>
      ))}
    </group>
  );
}

/**
 * Per-frame bridge: writes azimuth into the HUD span and projects
 * anchor objects onto the DOM hotspot buttons. Zero React state.
 */
function Projector({
  azRef,
  anchors,
  nodes,
}: {
  azRef: React.RefObject<HTMLSpanElement | null>;
  anchors: React.RefObject<AnchorRegistry>;
  nodes: React.RefObject<NodeRegistry>;
}) {
  const v = useMemo(() => new THREE.Vector3(), []);
  const controls = useThree(
    (s) => s.controls,
  ) as { getAzimuthalAngle?: () => number } | null;
  useFrame(({ camera, size }) => {
    if (azRef.current && controls?.getAzimuthalAngle) {
      const az = controls.getAzimuthalAngle() * (180 / Math.PI);
      azRef.current.textContent = ((az + 360) % 360).toFixed(1);
    }
    const registry = nodes.current;
    const points = anchors.current;
    for (const id of Object.keys(registry)) {
      const obj = points[id];
      const el = registry[id];
      if (!obj || !el) continue;
      obj.getWorldPosition(v);
      v.project(camera);
      const behind = v.z > 1;
      const x = (v.x * 0.5 + 0.5) * size.width;
      const y = (-v.y * 0.5 + 0.5) * size.height;
      // eslint-disable-next-line react-hooks/immutability -- DOM nodes are an external system; imperative placement is the intended bridge
      el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, -50%)`;
      el.style.opacity = behind ? "0" : "1";
      el.style.pointerEvents = behind ? "none" : "auto";
    }
  });
  return null;
}

/** Widens FOV on narrow viewports so the specimen stays framed. */
function AdaptiveFov() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  useFrame(() => {
    const aspect = size.width / Math.max(1, size.height);
    const target = aspect < 0.75 ? 46 : aspect < 1.1 ? 40 : 34;
    if (Math.abs(camera.fov - target) > 0.1) {
      // eslint-disable-next-line react-hooks/immutability -- three.js camera is an external system; tuning FOV imperatively is the standard R3F pattern
      camera.fov = target;
      camera.updateProjectionMatrix();
    }
  });
  return null;
}

export default function HeadsetScene({
  explode,
  autoRotate,
  reducedMotion,
  selectedId,
  azimuthRef,
  anchors,
  nodes,
}: {
  explode: boolean;
  autoRotate: boolean;
  reducedMotion: boolean;
  selectedId: string | null;
  azimuthRef: React.RefObject<HTMLSpanElement | null>;
  anchors: React.RefObject<AnchorRegistry>;
  nodes: React.RefObject<NodeRegistry>;
}) {
  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{ position: [4.1, 1.25, 5.3], fov: 34 }}
      gl={{ antialias: true, alpha: true }}
      style={{ touchAction: "none" }}
    >
      <SceneContent
        explode={explode}
        autoRotate={autoRotate}
        reducedMotion={reducedMotion}
        selectedId={selectedId}
        azimuthRef={azimuthRef}
        anchors={anchors}
        nodes={nodes}
      />
    </Canvas>
  );
}

function SceneContent({
  explode,
  autoRotate,
  reducedMotion,
  selectedId,
  azimuthRef,
  anchors,
  nodes,
}: {
  explode: boolean;
  autoRotate: boolean;
  reducedMotion: boolean;
  selectedId: string | null;
  azimuthRef: React.RefObject<HTMLSpanElement | null>;
  anchors: React.RefObject<AnchorRegistry>;
  nodes: React.RefObject<NodeRegistry>;
}) {
  const explodeCur = useDamped(explode ? 1 : 0);

  return (
    <>
      <ambientLight intensity={0.9} />
      <directionalLight position={[5, 7, 4]} intensity={1.6} />
      <directionalLight position={[-6, 3, -5]} intensity={0.6} color="#d63a00" />
      <directionalLight position={[-4, 2, 6]} intensity={0.45} />
      <pointLight position={[0, -2.5, 3]} intensity={9} distance={9} />

      <Float
        speed={1.1}
        floatIntensity={0.35}
        rotationIntensity={0.15}
        floatingRange={[-0.05, 0.05]}
      >
        <Headset explodeCur={explodeCur} anchors={anchors} selectedId={selectedId} />
      </Float>

      <ScanRing paused={reducedMotion} />
      <StageRig />
      <ContactShadows
        position={[0, -1.57, 0]}
        opacity={0.42}
        scale={9}
        blur={2.6}
        far={3.4}
        color="#1a1c1f"
        frames={reducedMotion ? 1 : Infinity}
      />

      <OrbitControls
        makeDefault
        enableZoom={false}
        enablePan={false}
        enableDamping
        dampingFactor={0.08}
        minPolarAngle={0.95}
        maxPolarAngle={1.52}
        autoRotate={autoRotate && !reducedMotion}
        autoRotateSpeed={0.9}
        target={[0, 0.05, 0]}
      />
      <Projector azRef={azimuthRef} anchors={anchors} nodes={nodes} />
      <AdaptiveFov />
    </>
  );
}
