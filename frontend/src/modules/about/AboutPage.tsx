import { Link } from 'react-router-dom';

export default function AboutPage() {
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: 'var(--color-panel)', color: 'var(--color-text)' }}
    >
      <header
        className="flex items-center justify-between px-6 py-4 border-b"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <div className="flex items-center gap-2">
          <img src="/icon-map2drone.png" alt="Map2Drone" className="w-6 h-6" />
          <span className="font-semibold">Map2Drone</span>
        </div>
        <Link
          to="/"
          className="text-xs px-3 py-1.5 rounded font-medium transition-opacity hover:opacity-80"
          style={{ backgroundColor: '#4f8cff', color: '#fff' }}
        >
          Volver a la app
        </Link>
      </header>

      <main className="flex-1 max-w-3xl mx-auto px-6 py-8 text-sm space-y-6">
        <h1 className="text-2xl font-bold">Acerca de Map2Drone</h1>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Nuestra misión</h2>
          <p>
            Map2Drone nace para democratizar la planificación de vuelos de dron. Nuestro objetivo es
            ofrecer una herramienta gratuita, precisa y fácil de usar que permita a pilotos,
            topógrafos, agricultores y profesionales generar misiones de vuelo optimizadas en
            cuestión de minutos, sin necesidad de software costoso ni instalaciones complejas.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Qué ofrecemos</h2>
          <p>
            Map2Drone es un planificador de misiones basado en navegador que convierte polígonos
            dibujados sobre un mapa en cuadrículas de vuelo listas para exportar a Litchi CSV.
            Integramos datos de elevación del terreno para calcular altitudes AGL reales, soportamos
            patrones de cuadrícula simple y en cruz, y ofrecemos control total sobre parámetros de
            vuelo como distancia entre líneas, velocidad, altitud y ángulo.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Tecnología</h2>
          <p>
            La plataforma utiliza FastAPI y PostgreSQL con GeoAlchemy2 en el backend, y React con
            MapLibre GL en el frontend. Los datos de elevación se obtienen de Open-Elevation API,
            y los mapas base provienen de OpenTopoMap y Esri. Todo el proyecto es de código abierto.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Contacto</h2>
          <p>
            ¿Tienes preguntas, sugerencias o necesitas ayuda? Escríbenos a{' '}
            <span className="font-mono" style={{ color: '#4f8cff' }}>contacto@map2drone.app</span>.
            También puedes reportar problemas o contribuir en nuestro{' '}
            <a
              href="https://github.com/Maoco2/map2drone"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
              style={{ color: '#4f8cff' }}
            >
              repositorio de GitHub
            </a>.
          </p>
        </section>
      </main>

      <footer
        className="text-center py-4 text-xs border-t"
        style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
      >
        &copy; {new Date().getFullYear()} Map2Drone. All rights reserved.
      </footer>
    </div>
  );
}
