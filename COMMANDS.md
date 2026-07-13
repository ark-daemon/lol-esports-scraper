# `lol-scraper`

League of Legends esports scraper (<span style="font-weight: bold">gol.gg</span>, <span style="font-weight: bold">loltv.gg</span>, <span style="font-weight: bold">Leaguepedia</span>).

**Usage**:

```console
$ lol-scraper [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `export`: Export SQLite tables to Parquet.
* `status`: Show database row counts.
* `scrape`: Scrape one or more sources.

## `lol-scraper export`

Export SQLite tables to Parquet.

**Usage**:

```console
$ lol-scraper export [OPTIONS]
```

**Options**:

* `--out PATH`: Output directory for Parquet files.
* `--table TEXT`: Specific table(s) to export.
* `--help`: Show this message and exit.

## `lol-scraper status`

Show database row counts.

**Usage**:

```console
$ lol-scraper status [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `lol-scraper scrape`

Scrape one or more sources.

**Usage**:

```console
$ lol-scraper scrape [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `gol`: Scrape gol.gg (CloakBrowser + network JSON...
* `loltv`: Scrape loltv.gg (CloakBrowser + network...
* `leaguepedia`: Scrape Leaguepedia / Liquipedia LoL via...
* `all`: Scrape gol.gg, loltv.gg, and Leaguepedia...

### `lol-scraper scrape gol`

Scrape gol.gg (CloakBrowser + network JSON capture).

**Usage**:

```console
$ lol-scraper scrape gol [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

### `lol-scraper scrape loltv`

Scrape loltv.gg (CloakBrowser + network JSON capture).

**Usage**:

```console
$ lol-scraper scrape loltv [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

### `lol-scraper scrape leaguepedia`

Scrape Leaguepedia / Liquipedia LoL via httpx.

**Usage**:

```console
$ lol-scraper scrape leaguepedia [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

### `lol-scraper scrape all`

Scrape gol.gg, loltv.gg, and Leaguepedia in one pipeline run.

**Usage**:

```console
$ lol-scraper scrape all [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.
