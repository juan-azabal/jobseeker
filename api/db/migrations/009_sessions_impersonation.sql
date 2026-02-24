-- Allow admins to impersonate other users within their session.
-- NULL = not impersonating (normal state).
ALTER TABLE sessions ADD COLUMN impersonated_user_id INTEGER REFERENCES users(id);
