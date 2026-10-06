import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

function Starfield() {
  const positions = useMemo(() => {
    const count = 900;
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const radius = 18 + Math.random() * 16;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      arr[i * 3 + 2] = radius * Math.cos(phi);
    }
    return arr;
  }, []);

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.018} color="#9aa0a6" transparent opacity={0.42} sizeAttenuation />
    </points>
  );
}

function Globe() {
  const pointsRef = useRef<THREE.Points>(null);
  const arcsRef = useRef<THREE.Group>(null);

  const positions = useMemo(() => {
    const count = 1800;
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);
      const r = 1.6;
      arr[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      arr[i * 3 + 2] = r * Math.cos(phi);
    }
    return arr;
  }, []);

  const glowRegions = useMemo(() => {
    // Approximate Tunisia / France / MENA glow nodes
    const latLon = [
      [36.8, 10.2],
      [48.8, 2.3],
      [25.0, 45.0],
      [30.0, 31.2],
    ];
    return latLon.map(([lat, lon]) => {
      const phi = ((90 - lat) * Math.PI) / 180;
      const theta = ((lon + 180) * Math.PI) / 180;
      const r = 1.62;
      return new THREE.Vector3(
        -r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta)
      );
    });
  }, []);

  useFrame(({ clock, pointer }) => {
    if (pointsRef.current) {
      pointsRef.current.rotation.y = clock.getElapsedTime() * 0.05 + pointer.x * 0.15;
      pointsRef.current.rotation.x = pointer.y * 0.08;
    }
    if (arcsRef.current) {
      arcsRef.current.rotation.y = clock.getElapsedTime() * 0.04;
    }
  });

  return (
    <group>
      <points ref={pointsRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.012} color="#c9a227" sizeAttenuation transparent opacity={0.85} />
      </points>
      <group ref={arcsRef}>
        {glowRegions.map((p, i) => (
          <mesh key={i} position={p}>
            <sphereGeometry args={[0.045, 16, 16]} />
            <meshBasicMaterial color="#e6c765" />
          </mesh>
        ))}
        {glowRegions.slice(0, -1).map((from, i) => {
          const to = glowRegions[i + 1];
          const mid = from.clone().add(to).multiplyScalar(0.5).normalize().multiplyScalar(2.1);
          const curve = new THREE.QuadraticBezierCurve3(from, mid, to);
          const pts = curve.getPoints(24);
          const geo = new THREE.BufferGeometry().setFromPoints(pts);
          return (
            <line key={`arc-${i}`}>
              <primitive object={geo} attach="geometry" />
              <lineBasicMaterial color="#c9a227" transparent opacity={0.55} />
            </line>
          );
        })}
      </group>
      <Starfield />
    </group>
  );
}

export default function HuntMapScene() {
  const visible = useRef(true);

  useEffect(() => {
    const onVis = () => {
      visible.current = document.visibilityState === "visible";
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [0, 0.4, 4.2], fov: 45 }}
      style={{ position: "absolute", inset: 0 }}
      frameloop="always"
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.setClearColor(0x000000, 0);
      }}
    >
      <ambientLight intensity={0.35} />
      <Globe />
    </Canvas>
  );
}
