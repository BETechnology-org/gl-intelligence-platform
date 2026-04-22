"use client";

import { useEffect, useRef, useState } from "react";
import type * as ThreeType from "three";

interface HeroPlatesProps {
  /** Overall canvas opacity — 1 for hero, lower for background decoration */
  opacity?: number;
  /** Tailwind positioning classes for the wrapper div */
  className?: string;
}

type IdleCallback = (cb: () => void, opts?: { timeout?: number }) => number;

interface IdleWindow {
  requestIdleCallback?: IdleCallback;
  cancelIdleCallback?: (id: number) => void;
}

export default function HeroPlates({
  opacity = 1,
  className = "absolute inset-y-0 right-[-18%] w-[75%] pointer-events-none",
}: HeroPlatesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  /* ── GATE: wait until wrapper is on-screen AND browser is idle ──
     Keeps three.js + gltf out of the LCP critical path. */
  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper || typeof window === "undefined") return;

    let cancelled = false;
    let idleId: number | null = null;
    const w = window as unknown as IdleWindow;

    const trigger = () => {
      if (cancelled) return;
      const schedule = w.requestIdleCallback;
      if (schedule) {
        idleId = schedule(() => !cancelled && setReady(true), { timeout: 1500 });
      } else {
        window.setTimeout(() => !cancelled && setReady(true), 300);
      }
    };

    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          trigger();
          io.disconnect();
        }
      },
      { root: null, threshold: 0, rootMargin: "200px" },
    );
    io.observe(wrapper);

    return () => {
      cancelled = true;
      io.disconnect();
      if (idleId !== null && w.cancelIdleCallback) w.cancelIdleCallback(idleId);
    };
  }, []);

  /* ── SCENE: three.js loaded only after the gate ── */
  useEffect(() => {
    if (!ready) return;
    const canvas = canvasRef.current;
    const wrapper = wrapperRef.current;
    if (!canvas || !wrapper) return;

    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    try {
      const probe = document.createElement("canvas");
      const ok = !!(probe.getContext("webgl2") || probe.getContext("webgl"));
      if (!ok) return;
    } catch {
      return;
    }

    let disposed = false;
    let cleanup: (() => void) | null = null;

    (async () => {
      const THREE = await import("three");
      const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");
      if (disposed) return;

      let renderer: InstanceType<typeof THREE.WebGLRenderer>;
      try {
        renderer = new THREE.WebGLRenderer({
          canvas,
          antialias: true,
          alpha: true,
          powerPreference: "high-performance",
        });
      } catch {
        return;
      }
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(canvas.offsetWidth, canvas.offsetHeight);
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
      renderer.outputColorSpace = THREE.SRGBColorSpace;

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(
        42,
        canvas.offsetWidth / canvas.offsetHeight,
        0.1,
        200,
      );
      camera.position.set(-2.8, 1.2, 9);
      camera.lookAt(1.5, 0, 0);

      /* ── PROCEDURAL STUDIO HDRI ── */
      const envW = 512;
      const envH = 256;
      const envData = new Float32Array(envW * envH * 4);
      const sb = (
        px: number,
        py: number,
        cx: number,
        cy: number,
        hw: number,
        hh: number,
        i: number,
      ) => {
        const fx = 1 - THREE.MathUtils.smoothstep(Math.abs(px - cx), hw * 0.7, hw);
        const fy = 1 - THREE.MathUtils.smoothstep(Math.abs(py - cy), hh * 0.7, hh);
        return fx * fy * i;
      };
      for (let y = 0; y < envH; y++) {
        for (let x = 0; x < envW; x++) {
          const u = x / envW;
          const v = y / envH;
          const idx = (y * envW + x) * 4;
          let r = 0.002;
          let g = 0.002;
          let b = 0.003;
          const k = sb(u, v, 0.18, 0.15, 0.14, 0.1, 5.5);
          r += k * 1.0; g += k * 0.85; b += k * 0.6;
          const f = sb(u, v, 0.8, 0.35, 0.09, 0.18, 1.4);
          r += f * 0.65; g += f * 0.72; b += f * 0.95;
          const rim = sb(u, v, 0.5, 0.06, 0.38, 0.025, 2.2);
          r += rim * 0.8; g += rim * 0.88; b += rim * 1.0;
          envData[idx] = r; envData[idx + 1] = g; envData[idx + 2] = b; envData[idx + 3] = 1;
        }
      }
      const envTex = new THREE.DataTexture(envData, envW, envH, THREE.RGBAFormat, THREE.FloatType);
      envTex.mapping = THREE.EquirectangularReflectionMapping;
      envTex.needsUpdate = true;
      scene.environment = envTex;

      /* ── BRUSHED METAL NORMAL + ROUGHNESS ── */
      const buildMetalMaps = (size: number) => {
        const nc = document.createElement("canvas");
        nc.width = nc.height = size;
        const nCtx = nc.getContext("2d")!;
        const rc = document.createElement("canvas");
        rc.width = rc.height = size;
        const rCtx = rc.getContext("2d")!;
        nCtx.fillStyle = "#8080ff";
        nCtx.fillRect(0, 0, size, size);
        rCtx.fillStyle = "#555555";
        rCtx.fillRect(0, 0, size, size);
        for (let i = 0; i < 2500; i++) {
          const y = Math.random() * size;
          const x = Math.random() * size * 0.3;
          const w = Math.random() * size * 0.7 + size * 0.1;
          const h = Math.random() * 1.0 + 0.3;
          const ny = Math.floor(Math.random() * 36 + 110);
          nCtx.fillStyle = `rgba(128,${ny},255,${Math.random() * 0.1 + 0.02})`;
          nCtx.fillRect(x, y, w, h);
          const rv = Math.floor(Math.random() * 60 + 65);
          rCtx.fillStyle = `rgba(${rv},${rv},${rv},${Math.random() * 0.12 + 0.03})`;
          rCtx.fillRect(x, y, w, h);
        }
        for (let i = 0; i < 300; i++) {
          const x1 = Math.random() * size;
          const y1 = Math.random() * size;
          const angle = (Math.random() - 0.5) * 0.3;
          const len = Math.random() * 100 + 20;
          nCtx.beginPath();
          nCtx.moveTo(x1, y1);
          nCtx.lineTo(x1 + Math.cos(angle) * len, y1 + Math.sin(angle) * len);
          nCtx.strokeStyle = `rgba(135,115,255,${Math.random() * 0.08 + 0.02})`;
          nCtx.lineWidth = 0.5;
          nCtx.stroke();
        }
        const nTex = new THREE.CanvasTexture(nc);
        nTex.wrapS = nTex.wrapT = THREE.RepeatWrapping;
        nTex.repeat.set(3, 3);
        const rTex = new THREE.CanvasTexture(rc);
        rTex.wrapS = rTex.wrapT = THREE.RepeatWrapping;
        rTex.repeat.set(3, 3);
        return { nTex, rTex };
      };
      const { nTex: normalMap, rTex: roughMap } = buildMetalMaps(1024);

      const goldMat = new THREE.MeshStandardMaterial({
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

      const modelGroup = new THREE.Group();
      scene.add(modelGroup);

      const loader = new GLTFLoader();
      loader.load(
        "/hero-model.gltf",
        (gltf) => {
          if (disposed) return;
          const model = gltf.scene;
          model.traverse((child) => {
            if ((child as ThreeType.Mesh).isMesh) {
              const mesh = child as ThreeType.Mesh;
              mesh.material = goldMat;
              mesh.castShadow = true;
              mesh.receiveShadow = true;
            }
          });
          const box = new THREE.Box3().setFromObject(model);
          const sz = new THREE.Vector3();
          box.getSize(sz);
          const maxDim = Math.max(sz.x, sz.y, sz.z);
          model.scale.setScalar(9.0 / maxDim);
          model.updateMatrixWorld();
          const box2 = new THREE.Box3().setFromObject(model);
          const center = new THREE.Vector3();
          box2.getCenter(center);
          model.position.sub(center);
          model.rotation.z = -1.2;
          modelGroup.add(model);
        },
        undefined,
        (err) => {
          console.warn("[HeroPlates] model load error:", err);
        },
      );

      const key = new THREE.SpotLight(0xfff0c0, 700, 40, Math.PI / 4, 0.7, 1.5);
      key.position.set(-6, 10, 6);
      key.castShadow = true;
      key.shadow.mapSize.set(2048, 2048);
      key.shadow.bias = -0.0002;
      key.shadow.radius = 4;
      scene.add(key);
      key.target.position.set(0, 0, 0);
      scene.add(key.target);

      const fill = new THREE.SpotLight(0xc0d0f0, 160, 25, Math.PI / 5, 0.9, 1.5);
      fill.position.set(7, 3, 3);
      scene.add(fill);
      fill.target.position.set(0, 0, 0);
      scene.add(fill.target);

      const rim = new THREE.SpotLight(0xaabbdd, 280, 28, Math.PI / 7, 0.6, 1.5);
      rim.position.set(-1, 8, -7);
      scene.add(rim);
      rim.target.position.set(0, 0, 0);
      scene.add(rim.target);

      const kicker = new THREE.PointLight(0xddc070, 18, 12, 2);
      kicker.position.set(2, -3, 3);
      scene.add(kicker);
      scene.add(new THREE.AmbientLight(0x080810, 0.2));

      let scrollProgress = 0;
      const onScroll = () => {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        scrollProgress = max > 0 ? Math.min(window.scrollY / max, 1) : 0;
      };
      window.addEventListener("scroll", onScroll, { passive: true });

      let onScreen = true;
      let tabVisible = !document.hidden;
      const io = new IntersectionObserver(
        (entries) => {
          onScreen = entries[0]?.isIntersecting ?? true;
        },
        { root: null, threshold: 0 },
      );
      io.observe(wrapper);
      const onVisibility = () => {
        tabVisible = !document.hidden;
      };
      document.addEventListener("visibilitychange", onVisibility);

      const clock = new THREE.Clock();
      let rafId = 0;
      const targetRotY = { v: 0 };
      const currentRotY = { v: 0 };
      const targetRotX = { v: 0 };
      const currentRotX = { v: 0 };

      const animate = () => {
        rafId = requestAnimationFrame(animate);
        if (!onScreen || !tabVisible) return;
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
      };

      if (prefersReducedMotion) {
        const renderOnce = () => renderer.render(scene, camera);
        renderOnce();
        setTimeout(renderOnce, 250);
        setTimeout(renderOnce, 1200);
      } else {
        animate();
      }

      const onResize = () => {
        const w = canvas.offsetWidth;
        const h = canvas.offsetHeight;
        if (w === 0 || h === 0) return;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      };
      window.addEventListener("resize", onResize, { passive: true });

      cleanup = () => {
        cancelAnimationFrame(rafId);
        window.removeEventListener("scroll", onScroll);
        window.removeEventListener("resize", onResize);
        document.removeEventListener("visibilitychange", onVisibility);
        io.disconnect();
        envTex.dispose();
        normalMap.dispose();
        roughMap.dispose();
        goldMat.dispose();
        scene.traverse((obj) => {
          const mesh = obj as ThreeType.Mesh;
          if (mesh.geometry) mesh.geometry.dispose();
        });
        renderer.dispose();
      };
    })();

    return () => {
      disposed = true;
      if (cleanup) cleanup();
    };
  }, [ready, opacity]);

  return (
    <div ref={wrapperRef} className={`${className} pointer-events-none`} aria-hidden="true">
      <canvas ref={canvasRef} className="w-full h-full" />
    </div>
  );
}
