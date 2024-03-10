CREATE TABLE "dropbox" (
  "id" int NOT NULL AUTO_INCREMENT,
  "desktop_path" varchar(300) NOT NULL,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "status" enum('pending','done','deleted') DEFAULT 'done',
  "filename" varchar(300) NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE KEY "desktop_path" ("desktop_path"),
  KEY "filename_index" ("filename"),
  KEY "status_index" ("status")
);

CREATE TABLE "dropbox_cursors" (
  "id" int NOT NULL AUTO_INCREMENT,
  "dropbox_cursor" varchar(500) NOT NULL,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("id"),
  UNIQUE KEY "dropbox_cursor" ("dropbox_cursor"),
  KEY "idx_created_at_desc" ("created_at" DESC)
)
