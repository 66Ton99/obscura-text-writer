"""Read-only semantic journal checks against immutable captured provenance."""
from ..memory.journal import load_memory,validate_memory_journal
from ..memory.series_start import SERIES_START_KIND,read_series_start


def check_memory_versions(report,root,versions):
    from .integrity import contained_path
    for ref in versions.values():
        if ref.kind!='memory':continue
        try:
            journal=load_memory(contained_path(root,ref.relative_path).read_text(encoding='utf-8'))
            sources={}
            owners=[]
            prose_ids=[]
            for position,id in enumerate(journal.source_prose_ids):
                source=versions.get(id)
                if position==0 and source and source.kind==SERIES_START_KIND and source.story_id==ref.story_id and source.scene_id is None:
                    # SERIES: the start snapshot of a series book is scene 0 — only the first source, no scene owner.
                    sources[id]=read_series_start(contained_path(root,source.relative_path).read_text(encoding='utf-8'),id).text
                    continue
                if not source or source.story_id!=ref.story_id or source.kind not in {'manual','edited'} or not source.scene_id:
                    raise ValueError('Invalid memory source')
                sources[id]=contained_path(root,source.relative_path).read_text(encoding='utf-8')
                owners.append(source.scene_id)
                prose_ids.append(id)
            if not owners or owners[-1]!=ref.scene_id or len(owners)!=len(set(owners)):
                raise ValueError('Memory does not end with its own scene or repeats a scene')
            validate_memory_journal(journal,sources)
            snapshot=ref.dependency_snapshot
            if snapshot and snapshot.scope=='memory':
                heads={s.owner_id:s.expected for s in snapshot.selectors if s.kind=='head' and s.field=='prose'}
                from ..memory.reuse import approved_source_pairs
                pairs=approved_source_pairs(snapshot.memory_provenance)
                if owners!=snapshot.scene_order or any(
                        old!=heads.get(owner) and (old,heads.get(owner)) not in pairs
                        for owner,old in zip(owners,prose_ids)):
                    raise ValueError('Memory breaks the fixed scene prefix')
            else:
                report.limitations.append(ref.id+': the historical order of legacy memory without a snapshot is not proven; sources and quotes are verified.')
        except (ValueError,KeyError,OSError,TypeError):
            report.add('invalid_memory',ref.id,'Invalid memory log, prefix or proof')
