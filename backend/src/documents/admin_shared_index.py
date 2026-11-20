"""Extend the shared corpus, reusing existing vectors and immutable source recipes."""
import uuid

from .admin_ingestion import canonical


async def merge_shared(conn, target, base_corpus, settings, *, extra_indices=()):
    from .corpus_manifest import read_manifest, register_manifest
    from .shared_source import read_release_root, envelope
    base = await conn.fetchrow('''SELECT cv.index_version_id,iv.chunker_version,iv.embedding_model,
        cv.status AS corpus_status,iv.status AS index_status FROM public.corpus_versions cv
        JOIN public.index_versions iv USING(index_version_id) WHERE corpus_version_id=$1''',uuid.UUID(base_corpus))
    if (not base or base['chunker_version'] != 'shared-source-v1'
            or base['embedding_model'] != settings.embedding_model_ref
            or base['corpus_status'] != 'FROZEN' or base['index_status'] != 'ACTIVE'):
        raise ValueError('SHARED_BASE_NOT_COMPATIBLE')
    origin = str(base['index_version_id'])
    root = dict(await read_release_root(conn,origin,{}))
    target_id = uuid.UUID(target)
    # Source rows remain immutable. New version has its own IDs; copying is on
    # the DB server, without recomputing existing embeddings or transferring them.
    indices = list(dict.fromkeys([uuid.UUID(str(i)) for i in extra_indices] + [base['index_version_id']]))
    await conn.execute('''INSERT INTO public.text_chunks
        (chunk_id,document_id,index_version_id,chunk_index,page_number,section_label,
         token_count,char_start,char_end,content_hash,embedding,created_at,locator_json)
        SELECT md5('shared:' || $1::uuid::text || ':' || t.chunk_id::text)::uuid,
            t.document_id,$1,t.chunk_index,t.page_number,t.section_label,
            t.token_count,t.char_start,t.char_end,t.content_hash,t.embedding,now(),t.locator_json
        FROM (SELECT DISTINCT ON(document_id,chunk_index) * FROM public.text_chunks
              WHERE index_version_id=ANY($2::uuid[]) AND superseded_at IS NULL
              ORDER BY document_id,chunk_index,array_position($2::uuid[],index_version_id)) t
        WHERE NOT EXISTS(SELECT 1 FROM public.text_chunks existing
            WHERE existing.index_version_id=$1 AND existing.document_id=t.document_id
              AND existing.chunk_index=t.chunk_index AND existing.superseded_at IS NULL)''',target_id,indices)
    await conn.execute("UPDATE public.index_versions SET chunker_version='shared-source-v1' WHERE index_version_id=$1 AND status='BUILDING'",target_id)
    manifest = await read_manifest(conn,target,source_index_id=origin)
    await register_manifest(conn,manifest,'admin-'+target[:20])
    for table, key in [('corpus_facts','observation_id'),('corpus_prices','price_id')]:
        await conn.execute(f'''INSERT INTO public.{table}(corpus_version_id,{key},value_hash)
            SELECT $1,{key},value_hash FROM public.{table} WHERE corpus_version_id=$2
            ON CONFLICT DO NOTHING''',uuid.UUID(manifest['corpus_version_id']),uuid.UUID(base_corpus))
    root.update(index_version_id=target,corpus_version_id=manifest['corpus_version_id'],
                registered_manifest_sha256=manifest['manifest_sha256'],
                source_index_version_id=root.get('source_index_version_id',origin))
    binding=envelope('finmind:shared-source-release:'+target,root)
    await conn.execute('''INSERT INTO public.raw_payloads(payload_id,source_uri,sha256,payload,stored_at)
        VALUES($1,$2,$3,$4::jsonb,now())''',uuid.UUID(binding['payload_id']),binding['source_uri'],binding['sha256'],canonical(root))
    return manifest
