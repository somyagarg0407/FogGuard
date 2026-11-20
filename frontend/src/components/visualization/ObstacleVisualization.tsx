// 3D Obstacle Visualization using React Three Fiber
// Real-time zero-allocation Three.js pipeline with ADAS bounding cuboids & live HUD diagnostics
import { Component, useRef, useMemo, useState, useEffect, type ReactNode, type ErrorInfo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Grid } from '@react-three/drei';
import * as THREE from 'three';
import type { SensorReading } from '../../types';
import { warningLevelColor } from '../../utils';
import { useStore } from '../../store/useStore';

// Sensor zone 3D positions (relative to vehicle center)
// Car body is 1.8 wide (±0.9), 3.8 long. Front bumper at z=-1.9.
// front_left/front_right sit near headlight positions (x=±0.65), not far out to the sides.
const ZONE_POSITIONS: Record<string, [number, number, number]> = {
  front_left: [-0.65, 0.18, -1.95],
  front_center: [0, 0.18, -1.95],
  front_center_left: [-0.3, 0.18, -1.95],
  front_center_right: [0.3, 0.18, -1.95],
  front_right: [0.65, 0.18, -1.95],
  left_side: [-1.0, 0.35, 0],
  right_side: [1.0, 0.35, 0],
  roof_center: [0, 1.2, -1.0],
};

// Direction vectors: front sensors point almost straight forward.
// front_left/front_right have a very slight outward angle (not splayed wide).
const ZONE_DIRECTIONS: Record<string, [number, number, number]> = {
  front_left: [-0.08, 0, -1],
  front_center: [0, 0, -1],
  front_center_left: [-0.04, 0, -1],
  front_center_right: [0.04, 0, -1],
  front_right: [0.08, 0, -1],
  left_side: [-1, 0, 0],
  right_side: [1, 0, 0],
  roof_center: [0, 0.05, -1],
};

const MAX_RANGE = 400;
const SCALE = 0.025; // cm to Three.js units (400cm = 10 units in 3D world)

// ─── Module-Level Shared Geometries (Zero-Garbage-Collection in Hot Loop) ─────
const STANDARD_BOX_GEOM = new THREE.BoxGeometry(1.6, 1.1, 2.4);
const ROOF_BOX_GEOM = new THREE.BoxGeometry(1.8, 1.2, 2.4);
const STANDARD_EDGES_GEOM = new THREE.EdgesGeometry(STANDARD_BOX_GEOM);
const ROOF_EDGES_GEOM = new THREE.EdgesGeometry(ROOF_BOX_GEOM);
const CORNER_BOX_GEOM = new THREE.BoxGeometry(0.15, 0.15, 0.15);
const RADAR_RING_GEOM = new THREE.RingGeometry(0.9, 1.05, 32);
const BADGE_PLANE_GEOM = new THREE.PlaneGeometry(1.4, 0.35);
const BEAM_CYLINDER_GEOM = new THREE.CylinderGeometry(0.3, 0.3, 1, 6);
const SENSOR_DOT_GEOM = new THREE.SphereGeometry(0.08, 12, 12);

// Reusable basic materials
const WHITE_BASIC_MAT = new THREE.MeshBasicMaterial({ color: '#ffffff' });
const BADGE_BG_MAT = new THREE.MeshBasicMaterial({
  color: '#020818',
  transparent: true,
  opacity: 0.85,
  side: THREE.DoubleSide,
});

// ─── React Error Boundary for 3D WebGL Canvas ───────────────────────────────
interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class CanvasErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Canvas 3D Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center bg-slate-950/90 text-slate-300">
          <div className="w-12 h-12 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center mb-3">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h3 className="font-semibold text-white mb-1">3D HUD Temporarily Unavailable</h3>
          <p className="text-xs text-slate-400 max-w-sm mb-4">
            {this.state.error?.message || 'WebGL context or rendering error encountered.'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-medium transition-colors"
          >
            Reload 3D HUD
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function Vehicle() {
  return (
    <group>
      {/* Car body */}
      <mesh position={[0, 0.35, 0]} castShadow>
        <boxGeometry args={[1.8, 0.5, 3.8]} />
        <meshStandardMaterial color="#1e40af" metalness={0.7} roughness={0.3} />
      </mesh>
      {/* Cabin / Roof */}
      <mesh position={[0, 0.85, -0.2]} castShadow>
        <boxGeometry args={[1.4, 0.5, 2.0]} />
        <meshStandardMaterial color="#1d4ed8" metalness={0.6} roughness={0.4} />
      </mesh>
      {/* Windshield glass */}
      <mesh position={[0, 0.85, -1.21]} rotation={[-Math.PI / 6, 0, 0]}>
        <planeGeometry args={[1.3, 0.55]} />
        <meshStandardMaterial color="#38bdf8" transparent opacity={0.6} roughness={0.1} />
      </mesh>
      {/* Wheels */}
      {[[-0.95, 0.15, -1.2], [0.95, 0.15, -1.2], [-0.95, 0.15, 1.2], [0.95, 0.15, 1.2]].map(([x, y, z], i) => (
        <mesh key={i} position={[x, y, z] as [number, number, number]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.32, 0.32, 0.25, 20]} />
          <meshStandardMaterial color="#0f172a" metalness={0.4} roughness={0.8} />
        </mesh>
      ))}
      {/* Headlights (glow in fog) */}
      {[[-0.65, 0.35, -1.91], [0.65, 0.35, -1.91]].map(([x, y, z], i) => (
        <mesh key={i} position={[x, y, z] as [number, number, number]}>
          <boxGeometry args={[0.3, 0.12, 0.05]} />
          <meshStandardMaterial color="#fef08a" emissive="#fef08a" emissiveIntensity={1.2} />
        </mesh>
      ))}
      {/* Front LIDAR / Ultrasonic Sensor Mount Bar */}
      <mesh position={[0, 0.18, -1.92]}>
        <boxGeometry args={[1.8, 0.08, 0.05]} />
        <meshStandardMaterial color="#06b6d4" emissive="#06b6d4" emissiveIntensity={0.6} />
      </mesh>
      {/* Roof Ultrasonic Sensor Mount */}
      <mesh position={[0, 1.15, -0.9]}>
        <boxGeometry args={[0.25, 0.12, 0.25]} />
        <meshStandardMaterial color="#06b6d4" emissive="#06b6d4" emissiveIntensity={0.8} />
      </mesh>
    </group>
  );
}

function SensorBeam({ zone, sensor }: { zone: string; sensor: SensorReading }) {
  const meshRef = useRef<THREE.Mesh>(null);

  const startPos = ZONE_POSITIONS[zone] as [number, number, number];
  const dir = ZONE_DIRECTIONS[zone] as [number, number, number];

  const dist = sensor.distance_cm ?? MAX_RANGE;
  const beamLength = Math.min(dist, MAX_RANGE) * SCALE;
  const color = warningLevelColor(sensor.warning_level);

  const midPoint: [number, number, number] = [
    startPos[0] + (dir[0] * beamLength) / 2,
    startPos[1],
    startPos[2] + (dir[2] * beamLength) / 2,
  ];

  useFrame(({ clock }) => {
    if (meshRef.current && meshRef.current.material) {
      const alpha = sensor.obstacle_detected
        ? 0.35 + 0.25 * Math.sin(clock.getElapsedTime() * 4)
        : 0.08;
      (meshRef.current.material as THREE.MeshStandardMaterial).opacity = alpha;
    }
  });

  const isSideBeam = Math.abs(dir[2]) < 0.1;
  const rotation: [number, number, number] = isSideBeam ? [0, 0, Math.PI / 2] : [Math.PI / 2, 0, 0];
  const scale: [number, number, number] = isSideBeam
    ? [beamLength, 0.04, 0.04]
    : [0.04, beamLength, 0.04];

  return (
    <mesh
      ref={meshRef}
      geometry={BEAM_CYLINDER_GEOM}
      position={midPoint}
      rotation={rotation}
      scale={scale}
    >
      <meshStandardMaterial color={color} transparent opacity={0.15} />
    </mesh>
  );
}

// ─── 3D Vehicle Bounding Cuboid Revealed in Fog (Zero GC, Ref-Updated) ────────
function ObstacleCuboid({ zone, sensor }: { zone: string; sensor: SensorReading }) {
  const groupRef = useRef<THREE.Group>(null);
  const bodyMeshRef = useRef<THREE.Mesh>(null);
  const ringMeshRef = useRef<THREE.Mesh>(null);

  const hasObstacle =
    sensor.distance_cm !== null &&
    sensor.distance_cm > 0 &&
    sensor.distance_cm <= MAX_RANGE;

  const startPos = ZONE_POSITIONS[zone] ?? [0, 0, -2.5];
  const dir = ZONE_DIRECTIONS[zone] ?? [0, 0, -1];
  const safeDistance = Math.min(sensor.distance_cm ?? MAX_RANGE, MAX_RANGE);
  const dist = safeDistance * SCALE;

  const isRoofSensor = zone === 'roof_center';
  const isSideZone = zone === 'left_side' || zone === 'right_side';
  const size: [number, number, number] = isRoofSensor ? [1.8, 1.2, 2.4] : [1.6, 1.1, 2.4];
  const centerY = isRoofSensor ? 1.4 : size[1] / 2;

  // halfDepth: offset so the NEAREST FACE of the cuboid sits at the measured distance,
  // not the cuboid center. For side sensors, offset along X (size[0]/2); for forward sensors, offset along Z (size[2]/2).
  const halfDepth = isSideZone ? size[0] / 2 : size[2] / 2;

  const color = warningLevelColor(sensor.warning_level);
  const isCritical = sensor.warning_level === 'CRITICAL';
  const isWarning = sensor.warning_level === 'WARNING';

  // Select pre-allocated geometries
  const boxGeom = isRoofSensor ? ROOF_BOX_GEOM : STANDARD_BOX_GEOM;
  const edgesGeom = isRoofSensor ? ROOF_EDGES_GEOM : STANDARD_EDGES_GEOM;

  // Frame Loop: Smooth hover motion and direct transform updates
  useFrame(({ clock }) => {
    if (!groupRef.current) return;

    groupRef.current.visible = hasObstacle;
    if (!hasObstacle) return;

    const t = clock.getElapsedTime();
    // Position cuboid so its nearest face is at the measured distance (dist),
    // then push center out by halfDepth so the face closest to the car is correct.
    // dir is the normalized-ish direction vector. We need to normalize it for the offset.
    const dirLen = Math.sqrt(dir[0] * dir[0] + dir[1] * dir[1] + dir[2] * dir[2]);
    const nx = dir[0] / dirLen;
    const nz = dir[2] / dirLen;
    groupRef.current.position.set(
      startPos[0] + dir[0] * dist + nx * halfDepth,
      centerY + 0.02 * Math.sin(t * 3),
      startPos[2] + dir[2] * dist + nz * halfDepth
    );

    if (bodyMeshRef.current && bodyMeshRef.current.material) {
      const mat = bodyMeshRef.current.material as THREE.MeshStandardMaterial;
      const pulseSpeed = isCritical ? 8 : isWarning ? 5 : 2;
      const pulse = 0.5 + 0.5 * Math.sin(t * pulseSpeed);
      mat.emissiveIntensity = isCritical ? 0.6 + 0.4 * pulse : 0.3 + 0.2 * pulse;
    }
  });

  return (
    <group ref={groupRef} visible={hasObstacle}>
      {/* 1. Translucent Volumetric Vehicle Body */}
      <mesh ref={bodyMeshRef} geometry={boxGeom}>
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isCritical ? 0.8 : 0.4}
          transparent
          opacity={isCritical ? 0.55 : 0.35}
          metalness={0.2}
          roughness={0.4}
        />
      </mesh>

      {/* 2. High-Visibility Glowing Wireframe Cage */}
      <lineSegments geometry={edgesGeom}>
        <lineBasicMaterial color={color} linewidth={2} />
      </lineSegments>

      {/* 3. Corner Brackets (Targeting Reticles) */}
      <group>
        <mesh geometry={CORNER_BOX_GEOM} material={WHITE_BASIC_MAT} position={[size[0] / 2, size[1] / 2, -size[2] / 2]} />
        <mesh geometry={CORNER_BOX_GEOM} material={WHITE_BASIC_MAT} position={[-size[0] / 2, size[1] / 2, -size[2] / 2]} />
        <mesh geometry={CORNER_BOX_GEOM} material={WHITE_BASIC_MAT} position={[size[0] / 2, -size[1] / 2, -size[2] / 2]} />
        <mesh geometry={CORNER_BOX_GEOM} material={WHITE_BASIC_MAT} position={[-size[0] / 2, -size[1] / 2, -size[2] / 2]} />
      </group>

      {/* 4. Ground Projection Radar Ring */}
      <mesh
        ref={ringMeshRef}
        geometry={RADAR_RING_GEOM}
        position={[0, -size[1] / 2 + 0.02, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <meshBasicMaterial color={color} transparent opacity={0.6} side={THREE.DoubleSide} />
      </mesh>

      {/* 5. 3D Floating HUD Distance Badge */}
      <group position={[0, size[1] / 2 + 0.45, 0]}>
        <mesh geometry={BADGE_PLANE_GEOM} material={BADGE_BG_MAT} />
        <Text
          position={[0, 0, 0.02]}
          fontSize={0.16}
          color={color}
          anchorX="center"
          anchorY="middle"
        >
          {`${sensor.sensor_id}: ${Math.round(sensor.distance_cm ?? 0)} cm`}
        </Text>
      </group>
    </group>
  );
}

function SensorIndicator({ zone, sensor }: { zone: string; sensor: SensorReading }) {
  const pos = ZONE_POSITIONS[zone] ?? [0, 0, 0];
  const color = warningLevelColor(sensor.warning_level);
  const indicatorRef = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (indicatorRef.current && sensor.obstacle_detected) {
      const scale = 1 + 0.3 * Math.abs(Math.sin(clock.getElapsedTime() * 4));
      indicatorRef.current.scale.setScalar(scale);
    }
  });

  return (
    <group position={[pos[0], 0.05, pos[2]]}>
      <mesh ref={indicatorRef} geometry={SENSOR_DOT_GEOM} position={[0, 0.08, 0]}>
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={sensor.obstacle_detected ? 0.9 : 0.2}
        />
      </mesh>
      <Text
        position={[0, -0.18, 0]}
        fontSize={0.13}
        color="#94a3b8"
        anchorX="center"
        anchorY="middle"
      >
        {sensor.sensor_id}
      </Text>
    </group>
  );
}

function Scene({ sensors, fogDensity }: { sensors: SensorReading[]; fogDensity: number }) {
  const sensorMap = useMemo(() => {
    const m: Record<string, SensorReading> = {};
    for (const s of sensors) {
      m[s.zone] = s;
    }
    return m;
  }, [sensors]);

  return (
    <>
      {/* Atmospheric Fog Effect */}
      {fogDensity > 0 && (
        <fog
          attach="fog"
          args={[
            '#020818',
            12,
            Math.max(30, 60 / Math.max(0.2, fogDensity)),
          ]}
        />
      )}

      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 12, 5]} intensity={1.0} castShadow />
      <pointLight position={[0, 6, 0]} intensity={0.8} color="#38bdf8" />

      {/* Road Grid Floor */}
      <Grid
        args={[30, 30]}
        cellSize={1}
        cellThickness={0.5}
        cellColor="#0d2070"
        sectionSize={5}
        sectionThickness={1.2}
        sectionColor="#1d4ed8"
        fadeDistance={30}
        position={[0, -0.05, -5]}
      />

      {/* Ego Vehicle */}
      <Vehicle />

      {/* Sensor Beams, 3D Obstacle Cuboids, and Sensor Status Dots */}
      {Object.entries(ZONE_POSITIONS).map(([zone]) => {
        const sensor = sensorMap[zone];
        if (!sensor) return null;
        return (
          <group key={zone}>
            <SensorBeam zone={zone} sensor={sensor} />
            <ObstacleCuboid zone={zone} sensor={sensor} />
            <SensorIndicator zone={zone} sensor={sensor} />
          </group>
        );
      })}

      {/* Orbit Controls */}
      <OrbitControls
        enablePan={true}
        enableZoom={true}
        minDistance={3}
        maxDistance={30}
        maxPolarAngle={Math.PI / 2.15}
        target={[0, 0.5, -4]}
      />
    </>
  );
}

interface ObstacleVisualizationProps {
  sensors: SensorReading[];
}

export function ObstacleVisualization({ sensors }: ObstacleVisualizationProps) {
  const [fogDensity, setFogDensity] = useState(1.0);
  const [frameAgeMs, setFrameAgeMs] = useState(0);

  // Store diagnostics
  const {
    telemetryFps,
    backendLatencyMs,
    networkLatencyMs,
    telemetrySeq,
    lastPacketTime,
    dataSource,
  } = useStore();

  // Update frame age counter at 10 Hz
  useEffect(() => {
    const timer = setInterval(() => {
      if (lastPacketTime > 0) {
        setFrameAgeMs(Math.round(performance.now() - lastPacketTime));
      }
    }, 100);
    return () => clearInterval(timer);
  }, [lastPacketTime]);

  const activeObstacles = sensors.filter(
    (s) => s.distance_cm !== null && s.distance_cm > 0 && s.distance_cm <= MAX_RANGE
  );

  const totalLatencyMs = Math.round((backendLatencyMs + networkLatencyMs) * 10) / 10;

  return (
    <div className="w-full h-full relative">
      <CanvasErrorBoundary>
        <Canvas
          camera={{ position: [0, 8, 10], fov: 48 }}
          shadows={false} // Shadows disabled on live telemetry for max frame rate
          style={{ background: 'transparent' }}
          gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        >
          <Scene sensors={sensors} fogDensity={fogDensity} />
        </Canvas>
      </CanvasErrorBoundary>

      {/* Live Telemetry Performance HUD Bar (Top-Left) */}
      <div className="absolute top-3 left-3 flex flex-col gap-1.5 z-10 pointer-events-none">
        <div className="flex items-center gap-2 bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-cyan-500/30 text-xs shadow-lg">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-slate-300">
            <strong className="text-cyan-400 font-mono text-sm">{activeObstacles.length}</strong> 3D Vehicle Cuboids
          </span>
          <span className="text-slate-600">|</span>
          <span className="font-mono text-emerald-400 font-semibold">{telemetryFps.toFixed(1)} Hz</span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400 font-mono">#{telemetrySeq}</span>
        </div>

        {/* Latency & Freshness Sub-Bar */}
        <div className="flex items-center gap-2 bg-slate-950/80 backdrop-blur-md px-2.5 py-1 rounded-md border border-slate-800 text-[10px] text-slate-400 font-mono">
          <span>Backend: <strong className="text-cyan-300">{backendLatencyMs.toFixed(1)}ms</strong></span>
          <span className="text-slate-700">·</span>
          <span>E2E: <strong className="text-emerald-300">{totalLatencyMs}ms</strong></span>
          <span className="text-slate-700">·</span>
          <span>Age: <strong className={frameAgeMs < 250 ? 'text-emerald-400' : 'text-amber-400'}>{frameAgeMs}ms</strong></span>
          <span className="text-slate-700">·</span>
          <span className="uppercase text-[9px] px-1 py-0.2 rounded bg-slate-800 text-cyan-300">
            {dataSource === 'hardware' ? 'HARDWARE' : 'SIMULATION'}
          </span>
        </div>
      </div>

      {/* Fog Simulation Slider / Toggle in Top Bar */}
      <div className="absolute top-3 right-3 flex items-center gap-2 bg-slate-900/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700/60 text-xs text-slate-300 z-10">
        <span>Fog Density:</span>
        <button
          onClick={() => setFogDensity(0)}
          className={`px-2 py-0.5 rounded ${fogDensity === 0 ? 'bg-cyan-500 text-black font-semibold' : 'text-slate-400 hover:text-white'}`}
        >
          Clear
        </button>
        <button
          onClick={() => setFogDensity(1.0)}
          className={`px-2 py-0.5 rounded ${fogDensity === 1.0 ? 'bg-cyan-500 text-black font-semibold' : 'text-slate-400 hover:text-white'}`}
        >
          Normal
        </button>
        <button
          onClick={() => setFogDensity(1.8)}
          className={`px-2 py-0.5 rounded ${fogDensity === 1.8 ? 'bg-cyan-500 text-black font-semibold' : 'text-slate-400 hover:text-white'}`}
        >
          Heavy
        </button>
      </div>

    </div>
  );
}
