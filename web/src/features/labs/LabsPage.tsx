'use client';
/**
 * Labs: the expert calculations and research connectors, one at a time. A categorized list on the
 * left (above on phones) picks the tool kept in ?tool=; the panel on the right loads only that tool's
 * code. Connector tools keep the source gates of the former Markets page; tools that read the
 * selected profile sit behind ProfileGate like on their original pages.
 */
import './labs.css';
import dynamic from 'next/dynamic';
import { useCallback, useEffect, useRef, type ComponentType } from 'react';
import { useApp } from '../../state/app';
import { PageHeader, ProfileGate } from '../../components/common/Page';
import { Loading, Unavailable } from '../../components/common/States';
import { useTabParam } from '../../components/ui/Tabs';
import { readySource, useSourceCapabilities } from '../markets/SourceAvailability';
import { DEFAULT_LAB_TOOL, LAB_CATEGORIES, LAB_TOOLS, LAB_TOOL_IDS, visibleTools, type LabTool, type ToolContext } from './registry';

function ToolLoading() {
  const { tr } = useApp();
  return <Loading label={tr({ en: 'Opening the tool…', fr: 'Ouverture de l’outil…' })} />;
}

// One lazy component per tool, created once: the code of a tool is fetched the first time it opens.
const TOOL_VIEWS: ReadonlyMap<string, ComponentType<ToolContext>> = new Map(
  LAB_TOOLS.map(tool => [tool.id, dynamic(tool.loader, { ssr: false, loading: () => <ToolLoading /> })]));

const FALLBACK_TOOL = LAB_TOOLS.find(tool => tool.id === DEFAULT_LAB_TOOL) ?? LAB_TOOLS[0]!;

/** The list sits above the panel at this width (labs.css), so choosing a tool brings the panel into view. */
const STACKED_QUERY = '(max-width: 900px)';

export function LabsPage() {
  const { tr, profiles, windowCode } = useApp();
  const capabilities = useSourceCapabilities();
  const ready = useCallback((sourceId: string) => readySource(capabilities.data, sourceId), [capabilities.data]);
  const [toolId, setToolId] = useTabParam('tool', LAB_TOOL_IDS, DEFAULT_LAB_TOOL);
  const tool = LAB_TOOLS.find(item => item.id === toolId) ?? FALLBACK_TOOL;
  const panelHeading = useRef<HTMLHeadingElement | null>(null);
  const pendingScroll = useRef(false);

  const choose = (next: LabTool) => {
    pendingScroll.current = window.matchMedia(STACKED_QUERY).matches;
    setToolId(next.id);
  };
  useEffect(() => {
    const heading = panelHeading.current;
    if (!pendingScroll.current || !heading) return;
    pendingScroll.current = false;
    heading.focus({ preventScroll: true });
    const headerBottom = document.querySelector('.topbar')?.getBoundingClientRect().bottom ?? 0;
    window.scrollBy({ top: heading.getBoundingClientRect().top - headerBottom - 16 });
  }, [toolId]);

  const View = TOOL_VIEWS.get(tool.id);
  const context = (profile: ToolContext['profile']): ToolContext => ({ profile, profiles, ready, capabilities });
  // A profile tool starts afresh for another profile, a saved version or, when its figures depend on
  // it, another analysis period. The comparison chooses its own profiles, so it keeps its choice.
  const viewKey = (profileKey: string) => tool.needsProfile && tool.category !== 'comparison'
    ? `${tool.id}|${profileKey}|${tool.periodBound ? windowCode : ''}`
    : tool.id;

  let body;
  if (tool.gate && !capabilities.data && capabilities.loading) {
    body = <Loading label={tr({ en: 'Checking that the source is available…', fr: 'Vérification de la disponibilité de la source…' })} />;
  } else if (tool.gate && !ready(tool.gate)) {
    body = <Unavailable title={tr({ en: 'This source is not available in this session', fr: 'Cette source n’est pas disponible dans cette session' })}>
      <p>{tr({ en: 'Its capture is not documented today, so nothing is shown. Source availability lists what can be used.', fr: 'Sa capture n’est pas documentée aujourd’hui, donc rien n’est affiché. La disponibilité des sources indique ce qui peut servir.' })}</p>
      <button type="button" className="btn ghost labs-inline-btn" onClick={() => setToolId('source-availability')}>
        {tr({ en: 'See source availability', fr: 'Voir la disponibilité des sources' })}
      </button>
    </Unavailable>;
  } else if (!View) {
    body = null;
  } else if (tool.needsProfile) {
    body = <ProfileGate>{profile => <View key={viewKey(`${profile.profileId}|${profile.version}`)} {...context(profile)} />}</ProfileGate>;
  } else {
    body = <View key={viewKey('')} {...context(null)} />;
  }

  const ToolIcon = tool.icon;
  return <>
    <PageHeader tour="labs-header" title={tr({ en: 'Labs', fr: 'Labos' })}>
      <p className="page-sub">{tr({
        en: 'Expert calculations and research on documented sources. Nothing here is advice.',
        fr: 'Calculs experts et recherche sur des sources documentées. Rien ici n’est un conseil.',
      })}</p>
    </PageHeader>
    <div className="labs-layout">
      <nav className="labs-nav" aria-label={tr({ en: 'Lab tools', fr: 'Outils des Labos' })} data-tour="labs-list">
        {LAB_CATEGORIES.map(category => {
          const tools = visibleTools(category.id, ready);
          const checking = !capabilities.data && capabilities.loading && LAB_TOOLS.some(item => item.category === category.id && item.gate);
          if (tools.length === 0 && !checking) return null;
          const headingId = `labs-cat-${category.id}`;
          return <section key={category.id} className="labs-cat" aria-labelledby={headingId}>
            <h2 id={headingId} className="labs-cat-title">{tr(category.label)}</h2>
            <ul className="labs-tools">
              {tools.map(item => {
                const Icon = item.icon;
                const current = item.id === tool.id;
                return <li key={item.id}>
                  <button type="button" className="labs-tool-btn" aria-current={current ? 'true' : undefined} onClick={() => choose(item)}>
                    <Icon aria-hidden="true" size={18} strokeWidth={1.75} className="labs-tool-icon" />
                    <span className="labs-tool-text">
                      <span className="labs-tool-name">{tr(item.label)}</span>
                      <span className="labs-tool-purpose">{tr(item.purpose)}</span>
                    </span>
                  </button>
                </li>;
              })}
            </ul>
            {checking && <p className="small muted labs-checking" role="status">{tr({ en: 'Checking which sources are available…', fr: 'Vérification des sources disponibles…' })}</p>}
          </section>;
        })}
      </nav>
      <section className="labs-panel" aria-labelledby="labs-tool-title" data-tour="labs-tool">
        <header className="labs-panel-head">
          <span className="labs-panel-icon" aria-hidden="true"><ToolIcon size={20} strokeWidth={1.75} /></span>
          <div>
            <h2 id="labs-tool-title" className="labs-panel-title" ref={panelHeading} tabIndex={-1}>{tr(tool.label)}</h2>
            <p className="labs-panel-purpose">{tr(tool.purpose)}</p>
          </div>
        </header>
        <div key={tool.id} className="tab-panel labs-panel-body">{body}</div>
      </section>
    </div>
  </>;
}
