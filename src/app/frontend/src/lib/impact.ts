import { Kpis, Recomendacion } from './api';

/**
 * Traducción de una recomendación a impacto esperado.
 *
 * En un panel de ventas el impacto se mide en plata; aquí la moneda es la
 * ejecución: puntos porcentuales de disponibilidad, planograma o share of
 * shelf que la acción debería recuperar, y cuántos PDV toca. Los coeficientes
 * son los que D&N usa como regla de dedo en sus informes de campo.
 */
export type Impacto = {
  pp: number;              // puntos porcentuales recuperados
  metrica: string;         // sobre qué indicador aplica
  pdv: number;             // PDV alcanzados por la acción
  horizonte: string;       // en cuánto se espera ver el efecto
  confianza: 'baja' | 'media' | 'alta' | 'cualitativo';
  esProtectivo?: boolean;  // evita un deterioro en vez de sumar
  racional: string;
};

export function estimarImpacto(rec: Recomendacion, kpis: Kpis | null): Impacto {
  const sa: any = rec.suggested_action ?? {};
  const params = sa.params ?? {};
  const type = sa.type;
  const pdvRed = kpis?.pdv_visitados ?? 0;
  const pdvParam = Number(params.pdv ?? params.pdv_afectados ?? 0);
  const pdv = pdvParam || Math.max(1, Math.round(pdvRed * 0.15));

  if (type === 'visita_prioritaria') {
    // Reponer un quiebre devuelve el SKU al anaquel casi de inmediato; el
    // efecto sobre la disponibilidad de la categoría escala con los PDV.
    const cobertura = pdvRed ? pdv / pdvRed : 0.15;
    return {
      pp: cobertura * 100 * 0.6,
      metrica: 'disponibilidad',
      pdv,
      horizonte: '2 h',
      confianza: 'alta',
      racional: `reposición en ${pdv} PDV · 60% de los quiebres se resuelven en la primera visita`,
    };
  }

  if (type === 'corregir_planograma') {
    const cobertura = pdvRed ? pdv / pdvRed : 0.15;
    return {
      pp: cobertura * 100 * 0.8,
      metrica: 'planograma',
      pdv,
      horizonte: '4 h',
      confianza: 'alta',
      racional: `reacomodo guiado en ${pdv} PDV · corrección verificable en la misma visita`,
    };
  }

  if (type === 'ampliar_espacio') {
    const facings = Number(params.facings_extra ?? 1);
    return {
      pp: facings * 1.4,
      metrica: 'share of shelf',
      pdv,
      horizonte: '1 semana',
      confianza: 'media',
      racional: `+${facings} cara(s) negociada(s) · cada cara vale ~1.4 pp de SOS en la categoría`,
    };
  }

  if (type === 'ajustar_precio') {
    const actual = Number(params.precio_actual ?? params.indice_actual ?? 0);
    const sugerido = Number(params.precio_sugerido ?? params.indice_objetivo ?? actual);
    if (!actual || !sugerido || actual === sugerido) {
      return {
        pp: 0, metrica: 'índice de precio', pdv, horizonte: '1 semana',
        confianza: 'baja', racional: 'la acción no trae precio suficiente para estimar',
      };
    }
    const cierre = Math.abs((actual - sugerido) / actual) * 100;
    return {
      pp: cierre,
      metrica: 'índice de precio',
      pdv,
      horizonte: '1 semana',
      confianza: 'media',
      racional: `cierra ${cierre.toFixed(1)} pp de brecha contra la competencia en ${pdv} PDV`,
    };
  }

  if (type === 'activar_promo') {
    return {
      pp: 6,
      metrica: 'rotación',
      pdv,
      horizonte: '2 semanas',
      confianza: 'media',
      racional: 'activación promocional · +6 pp de rotación observados en ciclos comparables',
    };
  }

  if (type === 'respuesta_crisis') {
    return {
      pp: 4,
      metrica: 'sentimiento neto',
      pdv,
      horizonte: '48 h',
      confianza: 'cualitativo',
      esProtectivo: true,
      racional: 'contiene el deterioro de sentimiento antes de que llegue al anaquel',
    };
  }

  if (type === 'amplificar_contenido') {
    return {
      pp: 3,
      metrica: 'sentimiento neto',
      pdv,
      horizonte: '1 semana',
      confianza: 'baja',
      racional: 'amplificación de conversación positiva ya validada por engagement',
    };
  }

  return {
    pp: 0,
    metrica: 'ejecución',
    pdv,
    horizonte: 'n/d',
    confianza: 'baja',
    racional: 'tipo de acción sin modelo de impacto',
  };
}

// ---- Acciones despachadas (persisten en la sesión) --------------------------

export type AccionAprobada = {
  rec_id: string;
  aprobada_en: string; // ISO
  agent_name: string;
  title: string;
  action_type: string;
  impacto_pp: number;
  impacto_metrica: string;
  pdv: number;
  esProtectivo: boolean;
};

const STORE_KEY = 'dn.accionesAprobadas.v1';

export function cargarAcciones(): AccionAprobada[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return [];
    const corte = Date.now() - 24 * 3600_000;
    return arr.filter((a: any) => new Date(a.aprobada_en).getTime() > corte);
  } catch {
    return [];
  }
}

export function guardarAcciones(acciones: AccionAprobada[]) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(acciones));
  } catch {
    /* cuota agotada, no es crítico */
  }
}

export function limpiarAcciones() {
  try {
    localStorage.removeItem(STORE_KEY);
  } catch {
    /* ignorar */
  }
}
