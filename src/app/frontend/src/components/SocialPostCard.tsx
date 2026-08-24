import { Heart, Megaphone, Minus, ThumbsDown, ThumbsUp } from 'lucide-react';
import { SocialPost } from '../lib/api';
import { bandera, relTime } from '../lib/format';

// ---- Platform icons (inline SVG, no extra dep) ------------------------------
function TwitterIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}
function InstagramIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <rect x="2.5" y="2.5" width="19" height="19" rx="5" />
      <circle cx="12" cy="12" r="4.2" />
      <circle cx="17.5" cy="6.5" r="0.9" fill="currentColor" />
    </svg>
  );
}
function TiktokIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5.8 20.1a6.34 6.34 0 0 0 10.86-4.43v-7a8.16 8.16 0 0 0 4.77 1.52v-3.4a4.85 4.85 0 0 1-1.84-.5z" />
    </svg>
  );
}

const PLATFORM: Record<
  string,
  { Icon: (p: { className?: string }) => JSX.Element; bg: string; text: string; label: string }
> = {
  twitter:   { Icon: TwitterIcon,   bg: 'bg-white',                                              text: 'text-tinta',  label: 'X / Twitter' },
  instagram: { Icon: InstagramIcon, bg: 'bg-gradient-to-br from-fuchsia-600 via-pink-500 to-amber-500', text: 'text-white',     label: 'Instagram' },
  tiktok:    { Icon: TiktokIcon,    bg: 'bg-black',                                                 text: 'text-white',     label: 'TikTok' },
};

// ---- Sentiment styling ------------------------------------------------------
const SENT: Record<
  string,
  { bar: string; pillBg: string; pillText: string; pillBorder: string; Icon: typeof ThumbsUp; label: string; cardBgTint: string }
> = {
  positivo: {
    bar: 'before:bg-emerald-500 before:shadow-[0_0_18px_-2px_rgba(16,185,129,0.6)]',
    pillBg: 'bg-emerald-500/15',
    pillText: 'text-emerald-600',
    pillBorder: 'border-emerald-500/40',
    Icon: ThumbsUp,
    label: 'Positivo',
    cardBgTint: 'hover:bg-emerald-500/[0.025]',
  },
  negativo: {
    bar: 'before:bg-red-500 before:shadow-[0_0_18px_-2px_rgba(239,68,68,0.6)]',
    pillBg: 'bg-red-500/15',
    pillText: 'text-red-600',
    pillBorder: 'border-red-500/40',
    Icon: ThumbsDown,
    label: 'Negativo',
    cardBgTint: 'hover:bg-red-500/[0.025]',
  },
  neutral: {
    bar: 'before:bg-humo',
    pillBg: 'bg-dn-100/40',
    pillText: 'text-grafito',
    pillBorder: 'border-marco',
    Icon: Minus,
    label: 'Neutro',
    cardBgTint: '',
  },
};

// La marca del cliente se resalta; las de la competencia quedan en gris para
// que el ojo distinga de un vistazo de quien se está hablando.
function brandChipColor(esCliente: boolean): string {
  return esCliente
    ? 'border-dn-600/50 bg-dn-400/10 text-dn-600'
    : 'border-marco text-grafito';
}

function compactCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace('.0', '')}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace('.0', '')}k`;
  return String(n);
}

// -----------------------------------------------------------------------------

interface Props {
  post: SocialPost;
  /** Fabricante bajo medición: sus marcas se resaltan en la tarjeta. */
  cliente?: string;
  /** Abre el diálogo de campaña. Si no se pasa, la tarjeta es solo lectura. */
  onAmplificar?: (post: SocialPost) => void;
  yaTieneCampana?: boolean;
}

export default function SocialPostCard({
  post,
  cliente,
  onAmplificar,
  yaTieneCampana,
}: Props) {
  const platform = PLATFORM[post.platform] ?? PLATFORM.twitter;
  const sent = SENT[post.sentiment] ?? SENT.neutral;
  const followers = post.author_followers ?? 0;
  const bigInfluencer = followers >= 50_000;

  return (
    <article
      className={[
        'relative bg-white border border-marco rounded-lg pl-5 pr-4 py-3.5',
        'overflow-hidden transition-colors duration-150',
        // left bar via ::before pseudo-element
        'before:content-[""] before:absolute before:left-0 before:top-0 before:bottom-0 before:w-1',
        sent.bar,
        sent.cardBgTint,
        post.is_viral ? 'ring-1 ring-dn-400/30' : '',
      ].join(' ')}
    >
      <header className="flex items-start gap-3 mb-2.5">
        {/* Platform logo */}
        <div
          className={[
            'flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center',
            platform.bg, platform.text,
          ].join(' ')}
          title={platform.label}
        >
          <platform.Icon className="w-4 h-4" />
        </div>

        {/* Handle + meta */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-tinta font-semibold text-sm truncate">
              {post.author_handle}
            </span>
            <span
              className={`text-[10.5px] tabular-nums ${
                bigInfluencer ? 'text-dn-600 font-semibold' : 'text-humo'
              }`}
            >
              {compactCount(followers)} seg.
            </span>
            {bigInfluencer && (
              <span className="text-[9px] uppercase tracking-widest text-dn-600 font-bold">
                influencer
              </span>
            )}
            {post.is_viral && (
              <span className="px-1.5 py-px text-[9px] font-bold tracking-widest uppercase rounded bg-dn-400/20 text-dn-600 border border-dn-400/30">
                ⚡ viral
              </span>
            )}
          </div>
          <div className="text-[10.5px] uppercase tracking-widest text-humo mt-0.5">
            {platform.label}
          </div>
        </div>

        {/* Time */}
        <span className="text-[11px] text-humo tabular-nums shrink-0 mt-0.5">
          {relTime(post.posted_at)}
        </span>
      </header>

      {/* Content */}
      <p className="text-[13.5px] text-tinta leading-relaxed whitespace-pre-wrap break-words mb-3">
        {post.content}
      </p>

      {/* Footer: sentiment + engagement + brand */}
      <footer className="flex flex-wrap items-center gap-2 text-[11px]">
        <span
          className={[
            'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border',
            sent.pillBg, sent.pillText, sent.pillBorder,
            'font-medium',
          ].join(' ')}
        >
          <sent.Icon className="w-3 h-3" strokeWidth={2.5} />
          {sent.label}
          <span className="opacity-60 tabular-nums">
            ({post.sentiment_score >= 0 ? '+' : ''}
            {post.sentiment_score.toFixed(2)})
          </span>
        </span>

        <span className="inline-flex items-center gap-1 text-humo tabular-nums">
          <Heart className="w-3.5 h-3.5 text-red-600" strokeWidth={2} fill="currentColor" />
          {compactCount(post.engagement)}
        </span>

        {post.marca && (
          <span
            className={`inline-flex items-center gap-1 border rounded-full px-2 py-0.5 ml-auto font-medium ${brandChipColor(
              !!cliente && post.fabricante === cliente,
            )}`}
          >
            {post.country_code && <span>{bandera(post.country_code)}</span>}
            {post.marca}
          </span>
        )}

        {onAmplificar && (
          <button
            onClick={() => onAmplificar(post)}
            disabled={yaTieneCampana}
            title={
              yaTieneCampana
                ? 'Este post ya tiene una campaña activa'
                : 'Poner pauta detrás de este post'
            }
            className={[
              'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-medium',
              'transition-colors',
              yaTieneCampana
                ? 'border-marco bg-nieve text-humo cursor-default'
                : 'border-dn-600/40 text-dn-600 hover:bg-dn-600 hover:text-white hover:border-dn-600',
            ].join(' ')}
          >
            <Megaphone className="w-3 h-3" strokeWidth={2.5} />
            {yaTieneCampana ? 'con campaña' : 'amplificar'}
          </button>
        )}
      </footer>
    </article>
  );
}
