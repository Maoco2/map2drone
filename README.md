# Map2Drone

Plataforma SaaS profesional para planificación de vuelos fotogramétricos con drones.

## Stack

- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS + MapLibre GL
- **Backend:** Python + FastAPI + PostgreSQL + PostGIS
- **Auth:** JWT + OAuth (Google, GitHub, Microsoft)
- **Storage:** S3 / MinIO

## Desarrollo

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Base de Datos

```powershell
.\scripts\setup-db.ps1
```

## Arquitectura

Monorepo con frontend y backend en módulos independientes.

## Fases

| Fase | Descripción |
|------|-------------|
| 1 | MVP: mapa interactivo, polígonos, grilla, GSD, exportación Litchi |
| 2 | Motor fotogramétrico: optimización rutas, tiempo/baterías |
| 3 | Importación/Exportación: KML, KMZ, GeoJSON, GPX, WPML |
| 4 | Terreno y 3D: Terrain Following, DEM/DSM, Three.js |
| 5 | Simulador: animación vuelo, métricas en tiempo real |
| 6 | Colaboración: usuarios, organizaciones, roles |
| 7 | API pública y SDK |
| 8 | Enterprise: multi-dron, RTK/PPK, AI, reportes avanzados |
