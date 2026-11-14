-- Web chat history. Custom application JWTs are verified by the backend;
-- app.chat_user_id is scoped to a transaction after SET LOCAL ROLE.
-- Keep this schema outside the browser Data API's public tables.
CREATE SCHEMA IF NOT EXISTS research_chat;
REVOKE ALL ON SCHEMA research_chat FROM PUBLIC, anon, authenticated, service_role;

DO $migration$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'finmind_chat_runtime') THEN
    CREATE ROLE finmind_chat_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
  ELSIF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'finmind_chat_runtime'
                AND (rolcanlogin OR rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Existing chat role has unexpected privileges';
  END IF;
  EXECUTE format('GRANT finmind_chat_runtime TO %I', current_user);
END
$migration$;
GRANT USAGE ON SCHEMA research_chat TO finmind_chat_runtime;

CREATE TABLE IF NOT EXISTS research_chat.conversations (
  conversation_id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
  schema_version text NOT NULL DEFAULT '1.0' CHECK (schema_version = '1.0'),
  revision integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
  started_at timestamptz NOT NULL,
  saved_at timestamptz NOT NULL,
  metadata jsonb NOT NULL CHECK (jsonb_typeof(metadata) = 'object'),
  preview text NOT NULL DEFAULT '' CHECK (length(preview) <= 80),
  turns integer NOT NULL DEFAULT 0 CHECK (turns >= 0),
  lease_id uuid,
  lease_expires_at timestamptz,
  UNIQUE (conversation_id, user_id),
  CHECK ((lease_id IS NULL) = (lease_expires_at IS NULL))
);
CREATE INDEX IF NOT EXISTS chat_owner_saved_idx
  ON research_chat.conversations (user_id, saved_at DESC, conversation_id);

CREATE TABLE IF NOT EXISTS research_chat.messages (
  conversation_id uuid NOT NULL,
  user_id uuid NOT NULL,
  position integer NOT NULL CHECK (position >= 0 AND position < 2000),
  payload jsonb NOT NULL CHECK (
    jsonb_typeof(payload) = 'object'
    AND payload ?& ARRAY['role','content','timestamp']
    AND jsonb_typeof(payload->'role') = 'string'
    AND payload->>'role' IN ('user', 'assistant')
    AND jsonb_typeof(payload->'content') = 'string'
    AND jsonb_typeof(payload->'timestamp') = 'string'
    AND octet_length(payload::text) <= 2097152
  ),
  PRIMARY KEY (conversation_id, position),
  FOREIGN KEY (conversation_id, user_id)
    REFERENCES research_chat.conversations(conversation_id, user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS chat_message_owner_idx
  ON research_chat.messages(user_id, conversation_id, position);

ALTER TABLE research_chat.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_chat.conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE research_chat.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_chat.messages FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS conversation_owner ON research_chat.conversations;
CREATE POLICY conversation_owner ON research_chat.conversations TO finmind_chat_runtime
  USING (user_id = nullif(current_setting('app.chat_user_id', true), '')::uuid)
  WITH CHECK (user_id = nullif(current_setting('app.chat_user_id', true), '')::uuid);
DROP POLICY IF EXISTS message_owner ON research_chat.messages;
CREATE POLICY message_owner ON research_chat.messages TO finmind_chat_runtime
  USING (user_id = nullif(current_setting('app.chat_user_id', true), '')::uuid)
  WITH CHECK (user_id = nullif(current_setting('app.chat_user_id', true), '')::uuid);
REVOKE ALL ON ALL TABLES IN SCHEMA research_chat FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON research_chat.conversations, research_chat.messages TO finmind_chat_runtime;

CREATE TABLE IF NOT EXISTS research_chat.schema_migrations (
  version text PRIMARY KEY,
  sha256 text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON research_chat.schema_migrations FROM PUBLIC, anon, authenticated, service_role, finmind_chat_runtime;
