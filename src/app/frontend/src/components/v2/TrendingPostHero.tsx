import { Flame, Heart, Megaphone, Users } from 'lucide-react';
import { SocialPost } from '../../lib/api';
import { bandera, fmtNumber, relTime } from '../../lib/format';

const PLATFORM_BG: Record<string, string> = {
  twitter:   'bg-white',
  instagram: 'bg-gradient-to-br from-fuchsia-600 via-pink-500 to-amber-500',
  tiktok:    'bg-black',
};

const PLATFORM_LABEL: Record<string, string> = {
  twitter: 'X / Twitter',
  instagram: 'Instagram',
  tiktok: 'TikTok',
};

const SENT_BORDER: Record<string, string> = {
  positivo: 'border-emerald-500/50 shadow-[0_0_36px_-12px_rgba(16,185,129,0.55)]',
  negativo: 'border-red-500/50 shadow-[0_0_36px_-12px_rgba(239,68,68,0.55)]',
  neutral:  'border-marco',
};

const SENT_GLOW: Record<string, string> = {
  positivo: 'after:bg-emerald-500',
  negativo: 'after:bg-red-500',
  neutral:  'after:bg-dn-100',
};

interface Props {
  post: SocialPost;
  /** Abre el diálogo de campaña. Si no se pasa, la tarjeta es solo lectura. */
  onAmplificar?: (post: SocialPost) => void;
  /** El post ya tiene campaña: el botón se apaga y lo dice. */
  yaTieneCampana?: boolean;
}

export default function TrendingPostHero({ post, onAmplificar, yaTieneCampana }: Props) {
  return (
    <article
      className={[
        'relative rounded-xl border bg-white px-5 py-4 overflow-hidden',
        'after:content-[""] after:absolute after:left-0 after:top-0 after:bottom-0 after:w-1',
        SENT_BORDER[post.sentiment] ?? SENT_BORDER.neutral,
        SENT_GLOW[post.sentiment] ?? SENT_GLOW.neutral,
      ].join(' ')}
    >
      <header className="flex items-center gap-2.5 mb-3">
        <div className={`w-9 h-9 rounded-full flex items-center justify-center text-white text-[11px] font-bold ${PLATFORM_BG[post.platform] ?? 'bg-white'}`}>
          {(PLATFORM_LABEL[post.platform] ?? 'X')[0]}
        </div>
        <div className="leading-tight flex-1 min-w-0">
          <div className="text-tinta font-semibold text-sm truncate">
            {post.author_handle}
          </div>
          <div className="text-[10px] uppercase tracking-widest text-humo">
            {PLATFORM_LABEL[post.platform] ?? post.platform} · {relTime(post.posted_at)}
          </div>
        </div>
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-dn-400/20 text-dn-600 border border-dn-400/40 text-[10px] font-bold uppercase tracking-widest">
          <Flame className="w-3 h-3" strokeWidth={2.5} />
          viral
        </span>
      </header>

      <p className="text-[14px] text-tinta leading-relaxed line-clamp-3 mb-3">
        {post.content}
      </p>

      <footer className="flex items-center gap-4 text-[11px] text-grafito">
        <span className="inline-flex items-center gap-1 tabular-nums">
          <Heart className="w-3.5 h-3.5 text-red-600" strokeWidth={2} fill="currentColor" />
          {fmtNumber(post.engagement)}
        </span>
        {post.author_followers != null && (
          <span className="inline-flex items-center gap-1 tabular-nums">
            <Users className="w-3.5 h-3.5" strokeWidth={2} />
            {fmtNumber(post.author_followers)} seguidores
          </span>
        )}
        {post.marca && (
          <span className="ml-auto px-2 py-0.5 rounded-full border border-marco text-[10px] text-grafito">
            {post.country_code ? `${bandera(post.country_code)} ` : ''}{post.marca}
          </span>
        )}
      </footer>

      {onAmplificar && (
        <button
          onClick={() => onAmplificar(post)}
          disabled={yaTieneCampana}
          className={[
            'mt-3 w-full inline-flex items-center justify-center gap-1.5 rounded-lg',
            'px-3 py-2 text-[12px] font-semibold transition-colors',
            yaTieneCampana
              ? 'border border-marco bg-nieve text-humo cursor-default'
              : 'bg-dn-600 hover:bg-dn-700 text-white',
          ].join(' ')}
        >
          <Megaphone className="w-3.5 h-3.5" strokeWidth={2.5} />
          {yaTieneCampana ? 'Campaña en curso' : 'Amplificar y crear campaña'}
        </button>
      )}
    </article>
  );
}
