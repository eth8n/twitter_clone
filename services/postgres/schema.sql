-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS rum;

BEGIN;

-- Create users table (simplified version)
CREATE TABLE users (
    id_users BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    description TEXT,
    CONSTRAINT username_length CHECK (char_length(username) >= 3)
);

-- Create messages table (simplified version of tweets)
CREATE TABLE messages (
    id_messages BIGSERIAL PRIMARY KEY,
    id_users BIGINT REFERENCES users(id_users) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    content TEXT NOT NULL,
    CONSTRAINT content_length CHECK (char_length(content) > 0)
);

-- Create urls table
CREATE TABLE urls (
    id_urls BIGSERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    CONSTRAINT valid_url CHECK (url ~ '^https?://[^\s/$.?#].[^\s]*$')
);

-- Create message_urls table (simplified version of tweet_urls)
CREATE TABLE message_urls (
    id_messages BIGINT,
    id_urls BIGINT,
    PRIMARY KEY (id_messages, id_urls),
    FOREIGN KEY (id_messages) REFERENCES messages(id_messages) ON DELETE CASCADE,
    FOREIGN KEY (id_urls) REFERENCES urls(id_urls) ON DELETE CASCADE
);

-- Create indexes for fast querying
-- Index for chronological message retrieval
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);

-- Index for user lookup by username
CREATE INDEX idx_users_username ON users(username);

-- Index for message lookup by user
CREATE INDEX idx_messages_user_id ON messages(id_users);

-- Index for URL lookup by message
CREATE INDEX idx_message_urls_message_id ON message_urls(id_messages);

-- Create RUM index for full-text search on messages
CREATE INDEX idx_messages_content_rum ON messages USING rum(to_tsvector('english', content));

-- Create function to update message search vector
CREATE OR REPLACE FUNCTION messages_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector = to_tsvector('english', NEW.content);
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update search vector
CREATE TRIGGER messages_search_vector_update
    BEFORE INSERT OR UPDATE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION messages_search_vector_update();

-- Add search_vector column to messages table
ALTER TABLE messages ADD COLUMN search_vector tsvector;

COMMIT; 