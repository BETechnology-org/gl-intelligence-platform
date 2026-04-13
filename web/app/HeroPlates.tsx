"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

interface HeroPlatesProps {
  /** Overall canvas opacity — 1 for hero, lower for background decoration */
  opacity?: number;
  /** Tailwind positioning classes for the wrapper div */
  className?: string;
}

export default function HeroPlates({
  opacity = 1,
  className = "absolute inset-y-0 right-[-18%] w-[75%] pointer-events-none",
}: HeroPlatesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    /* ── RENDERER ── */
    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(canvas.offsetWidth, canvas.offsetHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    /* ── SCENE ── */
    const scene = new THREE.Scene();

    /* ── CAMERA ── */
    const camera = new THREE.PerspectiveCamera(
      42,
      canvas.offsetWidth / canvas.offsetHeight,
      0.1,
      200
    );
    camera.position.set(-2.8, 1.2, 9);
    camera.lookAt(1.5, 0, 0);

    /* ── PROCEDURAL STUDIO HDRI ── */
    const envW = 512, envH = 256;
    const envData = new Float32Array(envW * envH * 4);
    function sb(px: number, py: number, cx: number, cy: number, hw: number, hh: number, i: number) {
      const fx = 1 - THREE.MathUtils.smoothstep(Math.abs(px - cx), hw * 0.7, hw);
      const fy = 1 - THREE.MathUtils.smoothstep(Math.abs(py - cy), hh * 0.7, hh);
      return fx * fy * i;
    }
    for (let y = 0; y < envH; y++) {
      for (let x = 0; x < envW; x++) {
        const u = x / envW, v = y / envH, idx = (y * envW + x) * 4;
        let r = 0.002, g = 0.002, b = 0.003;
        const k = sb(u, v, 0.18, 0.15, 0.14, 0.1, 5.5);
        r += k * 1.0; g += k * 0.85; b += k * 0.6;
        const f = sb(u, v, 0.8, 0.35, 0.09, 0.18, 1.4);
        r += f * 0.65; g += f * 0.72; b += f * 0.95;
        const rim = sb(u, v, 0.5, 0.06, 0.38, 0.025, 2.2);
        r += rim * 0.8; g += rim * 0.88; b += rim * 1.0;
        envData[idx] = r; envData[idx+1] = g; envData[idx+2] = b; envData[idx+3] = 1;
      }
    }
    const envTex = new THREE.DataTexture(envData, envW, envH, THREE.RGBAFormat, THREE.FloatType);
    envTex.mapping = THREE.EquirectangularReflectionMapping;
    envTex.needsUpdate = true;
    scene.environment = envTex;

    /* ── BRUSHED METAL NORMAL + ROUGHNESS MAPS ── */
    function buildMetalMaps(size: number) {
      const nc = document.createElement("canvas"); nc.width = nc.height = size;
      const nCtx = nc.getContext("2d")!;
      const rc = document.createElement("canvas"); rc.width = rc.height = size;
      const rCtx = rc.getContext("2d")!;
      nCtx.fillStyle = "#8080ff"; nCtx.fillRect(0, 0, size, size);
      rCtx.fillStyle = "#555555"; rCtx.fillRect(0, 0, size, size);
      for (let i = 0; i < 2500; i++) {
        const y = Math.random() * size, x = Math.random() * size * 0.3;
        const w = Math.random() * size * 0.7 + size * 0.1, h = Math.random() * 1.0 + 0.3;
        const ny = Math.floor(Math.random() * 36 + 110);
        nCtx.fillStyle = `rgba(128,${ny},255,${Math.random() * 0.1 + 0.02})`; nCtx.fillRect(x, y, w, h);
        const rv = Math.floor(Math.random() * 60 + 65);
        rCtx.fillStyle = `rgba(${rv},${rv},${rv},${Math.random() * 0.12 + 0.03})`; rCtx.fillRect(x, y, w, h);
      }
      for (let i = 0; i < 300; i++) {
        const x1 = Math.random() * size, y1 = Math.random() * size;
        const angle = (Math.random() - 0.5) * 0.3, len = Math.random() * 100 + 20;
        nCtx.beginPath(); nCtx.moveTo(x1, y1); nCtx.lineTo(x1 + Math.cos(angle)*len, y1 + Math.sin(angle)*len);
        nCtx.strokeStyle = `rgba(135,115,255,${Math.random() * 0.08 + 0.02})`; nCtx.lineWidth = 0.5; nCtx.stroke();
      }
      const nTex = new THREE.CanvasTexture(nc); nTex.wrapS = nTex.wrapT = THREE.RepeatWrapping; nTex.repeat.set(3, 3);
      const rTex = new THREE.CanvasTexture(rc); rTex.wrapS = rTex.wrapT = THREE.RepeatWrapping; rTex.repeat.set(3, 3);
      return { nTex, rTex };
    }
    const { nTex: normalMap, rTex: roughMap } = buildMetalMaps(1024);

    /* ── PREMIUM CHAMPAGNE GOLD MATERIAL ── */
    const goldMat = new THREE.MeshStandardMaterial({
      // Lighter, more platinum-gold — less orange, more luminous
      color: new THREE.Color("#E2CC8A"),
      metalness: 0.98,
      roughness: 0.09,
      normalMap,
      roughnessMap: roughMap,
      normalScale: new THREE.Vector2(0.18, 0.18),
      envMapIntensity: 3.2,
      side: THREE.DoubleSide,
      transparent: opacity < 1,
      opacity,
    });

    /* ── LOAD GLTF ── */
    const loader = new GLTFLoader();
    const modelGroup = new THREE.Group();
    scene.add(modelGroup);

    loader.load("/hero-model.gltf", (gltf) => {
      const model = gltf.scene;

      model.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          mesh.material = goldMat;
          mesh.castShadow = true;
          mesh.receiveShadow = true;
        }
      });

      // 1. Measure raw bbox
      const box = new THREE.Box3().setFromObject(model);
      const size = new THREE.Vector3();
      box.getSize(size);

      // 2. Scale to fill frame
      const maxDim = Math.max(size.x, size.y, size.z);
      model.scale.setScalar(9.0 / maxDim);

      // 3. Re-center AFTER scaling so offset is correct regardless of scale factor
      model.updateMatrixWorld();
      const box2 = new THREE.Box3().setFromObject(model);
      const center = new THREE.Vector3();
      box2.getCenter(center);
      model.position.sub(center);

      model.rotation.z = -1.2;

      modelGroup.add(model);
    }, undefined, (err) => {
      console.error("[HeroPlates] load error:", err);
    });

    /* ── LIGHTS ── */
    const key = new THREE.SpotLight(0xFFF0C0, 700, 40, Math.PI / 4, 0.7, 1.5);
    key.position.set(-6, 10, 6);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.bias = -0.0002;
    key.shadow.radius = 4;
    scene.add(key); key.target.position.set(0, 0, 0); scene.add(key.target);

    const fill = new THREE.SpotLight(0xC0D0F0, 160, 25, Math.PI / 5, 0.9, 1.5);
    fill.position.set(7, 3, 3);
    scene.add(fill); fill.target.position.set(0, 0, 0); scene.add(fill.target);

    const rim = new THREE.SpotLight(0xAABBDD, 280, 28, Math.PI / 7, 0.6, 1.5);
    rim.position.set(-1, 8, -7);
    scene.add(rim); rim.target.position.set(0, 0, 0); scene.add(rim.target);

    const kicker = new THREE.PointLight(0xDDC070, 18, 12, 2);
    kicker.position.set(2, -3, 3);
    scene.add(kicker);
    scene.add(new THREE.AmbientLight(0x080810, 0.2));

    /* ── SCROLL ── */
    let scrollProgress = 0;
    const onScroll = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      scrollProgress = max > 0 ? Math.min(window.scrollY / max, 1) : 0;
    };
    window.addEventListener("scroll", onScroll, { passive: true });

    /* ── LOOP ── */
    const clock = new THREE.Clock();
    let rafId: number;
    const targetRotY = { v: 0 }, currentRotY = { v: 0 };
    const targetRotX = { v: 0 }, currentRotX = { v: 0 };

    function animate() {
      rafId = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      targetRotY.v = scrollProgress * Math.PI * 1.4;
      targetRotX.v = scrollProgress * 0.12;
      currentRotY.v += (targetRotY.v - currentRotY.v) * 0.05;
      currentRotX.v += (targetRotX.v - currentRotX.v) * 0.05;

      modelGroup.rotation.y = currentRotY.v;
      modelGroup.rotation.x = currentRotX.v;
      modelGroup.position.y = Math.sin(t * 0.4) * 0.06;

      camera.position.x = Math.sin(t * 0.1) * 0.15;
      camera.position.y = 1.2 + Math.cos(t * 0.08) * 0.08;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
    }

    animate();

    /* ── RESIZE ── */
    const onResize = () => {
      const w = canvas.offsetWidth, h = canvas.offsetHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
    };
  }, [opacity]);

  return (
    <div className={`${className} pointer-events-none`} aria-hidden="true">
      <canvas ref={canvasRef} className="w-full h-full" />
    </div>
  );
}
