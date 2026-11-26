-- ============================================================
--  Database Manajemen Antrian
--  Import lewat phpMyAdmin (tab Import) atau: mysql -u root < database.sql
-- ============================================================
CREATE DATABASE IF NOT EXISTS db_antrian
  CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE db_antrian;

DROP TABLE IF EXISTS antrian;
DROP TABLE IF EXISTS loket;
DROP TABLE IF EXISTS petugas;

-- 1) PETUGAS -------------------------------------------------
CREATE TABLE petugas (
  id_petugas INT AUTO_INCREMENT PRIMARY KEY,
  nama       VARCHAR(100) NOT NULL,
  username   VARCHAR(50)  NOT NULL UNIQUE,
  password   CHAR(64)     NOT NULL,              -- hash SHA-256
  status     ENUM('aktif','nonaktif') NOT NULL DEFAULT 'aktif'
) ENGINE=InnoDB;

-- 2) LOKET ---------------------------------------------------
CREATE TABLE loket (
  id_loket   INT AUTO_INCREMENT PRIMARY KEY,
  nama_loket VARCHAR(50) NOT NULL,
  status     ENUM('aktif','nonaktif') NOT NULL DEFAULT 'aktif'
) ENGINE=InnoDB;

-- 3) ANTRIAN -------------------------------------------------
CREATE TABLE antrian (
  id_antrian    INT AUTO_INCREMENT PRIMARY KEY,
  kode          CHAR(1) NOT NULL DEFAULT 'A',
  nomor         INT NOT NULL,
  tanggal       DATE NOT NULL,
  status        ENUM('menunggu','dipanggil','selesai','batal') NOT NULL DEFAULT 'menunggu',
  waktu_ambil   DATETIME NOT NULL,
  waktu_panggil DATETIME NULL,
  waktu_selesai DATETIME NULL,
  id_loket      INT NULL,
  id_petugas    INT NULL,
  UNIQUE KEY uq_nomor_harian (tanggal, kode, nomor),
  KEY idx_tanggal_status (tanggal, status),
  CONSTRAINT fk_antrian_loket   FOREIGN KEY (id_loket)   REFERENCES loket(id_loket)     ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_antrian_petugas FOREIGN KEY (id_petugas) REFERENCES petugas(id_petugas) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- DATA AWAL ---------------------------------------------------
INSERT INTO petugas (nama, username, password, status) VALUES
 ('Administrator', 'admin',   SHA2('admin123', 256),   'aktif'),
 ('Petugas Satu',  'petugas1', SHA2('petugas123', 256), 'aktif');

INSERT INTO loket (nama_loket, status) VALUES
 ('Loket 1', 'aktif'),
 ('Loket 2', 'aktif'),
 ('Loket 3', 'aktif');