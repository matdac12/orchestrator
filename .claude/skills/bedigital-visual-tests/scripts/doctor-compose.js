#!/usr/bin/env node
// doctor-compose.js — structural checks on a rendered `docker compose config
// --format json`, for `sandbox.sh doctor`. Reads the JSON on stdin and prints
// one "PASS|WARN|FAIL  <message>" line per finding. Node built-ins only (Node is
// already a skill dependency via build-report.js); the caller tallies by prefix.
//
// argv: node doctor-compose.js <APP_SERVICE> <APP_PORT>
// The caller renders the config with BDVT_RUN=doctor, so a per-run-templated
// container_name contains "doctor" and a literal fixed name does not.

const [, , appService, appPort] = process.argv;

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (d) => (raw += d));
process.stdin.on("end", () => {
  let cfg;
  try {
    cfg = JSON.parse(raw);
  } catch (e) {
    console.log("FAIL  could not parse compose config JSON: " + e.message);
    return;
  }
  const services = cfg.services || {};
  const names = Object.keys(services);
  if (!names.length) {
    console.log("FAIL  rendered compose defines no services");
    return;
  }

  const isEphemeral = (p) =>
    p.published === undefined || p.published === "" || String(p.published) === "0";

  // APP_SERVICE must exist and publish APP_PORT so the browser can reach it.
  const app = services[appService];
  if (!app) {
    console.log(
      `FAIL  APP_SERVICE '${appService}' is not a service (have: ${names.join(", ")})`,
    );
  } else {
    const pub = (app.ports || []).filter((p) => String(p.target) === String(appPort));
    if (!pub.length) {
      console.log(
        `FAIL  APP_SERVICE '${appService}' does not publish container port ${appPort} — the browser can't reach it (map "0:${appPort}")`,
      );
    } else if (pub.some(isEphemeral)) {
      console.log(
        `PASS  APP_SERVICE '${appService}' publishes ${appPort} on an ephemeral host port`,
      );
    } else {
      console.log(
        `WARN  APP_SERVICE '${appService}' publishes ${appPort} on FIXED host port(s) ${pub
          .map((p) => p.published)
          .join(",")} — use "0:${appPort}" so concurrent runs don't collide`,
      );
    }
  }

  // Per-service hygiene: fixed container_name, host bind-mounts, fixed ports.
  for (const [name, svc] of Object.entries(services)) {
    if (svc.container_name && !String(svc.container_name).includes("doctor")) {
      console.log(
        `WARN  service '${name}' sets a fixed container_name '${svc.container_name}' — global names break per-run isolation; template it as bdvt-\${BDVT_RUN}-${name}`,
      );
    }
    for (const v of svc.volumes || []) {
      if (v && v.type === "bind") {
        console.log(
          `WARN  service '${name}' host bind-mount ${v.source} -> ${v.target} — test the built image, not host files; drop with volumes: !reset [] (or !override)`,
        );
      }
    }
    if (name !== appService) {
      for (const p of svc.ports || []) {
        if (!isEphemeral(p)) {
          console.log(
            `WARN  service '${name}' publishes FIXED host port ${p.published}:${p.target} — internal services shouldn't publish; use ports: !reset [] or an ephemeral "0:" map`,
          );
        }
      }
    }
  }
});
