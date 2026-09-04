suppressPackageStartupMessages({
  library(edgeR)
  library(limma)
  library(readxl)
})

args <- commandArgs(trailingOnly = TRUE)
data_dir <- if (length(args) >= 1) args[[1]] else "geo_data"
out_dir <- if (length(args) >= 2) args[[2]] else "geo_results"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

targets <- data.frame(
  gene = c("VSP1","VSP2","LOX2","JAZ10","MYC2","PDF1.2","ORA59","ERF1"),
  AGI  = c("AT5G24780","AT5G24770","AT3G45140","AT5G13220","AT1G32640","AT5G44420","AT1G06160","AT3G23240"),
  stringsAsFactors = FALSE
)

stripq <- function(x) gsub('^"|"$', '', x)
read_geo_matrix <- function(path) {
  lines <- readLines(gzfile(path), warn = FALSE)
  b <- grep("!series_matrix_table_begin", lines, fixed = TRUE) + 1
  e <- grep("!series_matrix_table_end", lines, fixed = TRUE) - 1
  stopifnot(length(b) == 1, length(e) == 1, e >= b)
  z <- read.delim(text = paste(lines[b:e], collapse = "\n"), row.names = 1,
                  check.names = FALSE, quote = '"', stringsAsFactors = FALSE)
  storage.mode(z) <- "numeric"
  z
}
read_geo_field <- function(path, prefix) {
  lines <- readLines(gzfile(path), warn = FALSE)
  hit <- lines[startsWith(lines, prefix)][1]
  if (is.na(hit)) stop("Missing field: ", prefix)
  stripq(strsplit(hit, "\t", fixed = TRUE)[[1]][-1])
}
panel_bh <- function(p) {
  out <- rep(NA_real_, length(p))
  ok <- is.finite(p)
  out[ok] <- p.adjust(p[ok], method = "BH")
  out
}
write_table <- function(x, name) {
  write.csv(x, file.path(out_dir, name), row.names = FALSE, na = "")
}

# GSE33505: ATH1 MAS5, limma empirical Bayes.
mat335 <- read_geo_matrix(file.path(data_dir, "GSE33505_series_matrix.txt.gz"))
tit335 <- read_geo_field(file.path(data_dir, "GSE33505_series_matrix.txt.gz"), "!Sample_title")
stopifnot(ncol(mat335) == length(tit335))
colnames(mat335) <- tit335
is_hh24 <- grepl("healthy Lima bean", tit335, ignore.case = TRUE) & grepl("24h", tit335, ignore.case = TRUE)
is_hh48 <- grepl("healthy Lima bean", tit335, ignore.case = TRUE) & grepl("48h", tit335, ignore.case = TRUE)
is_lh24 <- grepl("leafminer", tit335, ignore.case = TRUE) & grepl("Lima bean", tit335, ignore.case = TRUE) & grepl("24h", tit335, ignore.case = TRUE)
is_lh48 <- grepl("leafminer", tit335, ignore.case = TRUE) & grepl("Lima bean", tit335, ignore.case = TRUE) & grepl("48h", tit335, ignore.case = TRUE)
keep335 <- is_hh24 | is_hh48 | is_lh24 | is_lh48
grp335 <- ifelse(is_hh24[keep335], "HH24",
          ifelse(is_hh48[keep335], "HH48",
          ifelse(is_lh24[keep335], "LH24", "LH48")))
expr335 <- log2(mat335[, keep335, drop = FALSE])
design335 <- model.matrix(~0 + factor(grp335, levels = c("HH24","LH24","HH48","LH48")))
colnames(design335) <- c("HH24","LH24","HH48","LH48")
fit335 <- eBayes(contrasts.fit(lmFit(expr335, design335),
                               makeContrasts(LH24-HH24, LH48-HH48, levels = design335)),
                  trend = TRUE, robust = TRUE)
probe335 <- c(VSP1="245928_s_at", VSP2="245928_s_at", LOX2="252618_at", JAZ10="250292_at",
              MYC2="261713_at", PDF1.2="249052_at", ORA59="260783_at", ERF1="257927_at")
res335 <- list()
for (k in 1:2) {
  tt <- topTable(fit335, coef = k, number = Inf, sort.by = "none", adjust.method = "BH")
  con <- c("LH24_vs_HH24","LH48_vs_HH48")[[k]]
  tmp <- data.frame(dataset="GSE33505", gene=targets$gene, AGI=targets$AGI,
                    contrast=con, probe=unname(probe335[targets$gene]),
                    log2FC=NA_real_, PValue=NA_real_, FDR_genome=NA_real_, stringsAsFactors=FALSE)
  for (i in seq_len(nrow(tmp))) {
    pr <- tmp$probe[i]
    if (pr %in% rownames(tt)) {
      tmp$log2FC[i] <- tt[pr, "logFC"]
      tmp$PValue[i] <- tt[pr, "P.Value"]
      tmp$FDR_genome[i] <- tt[pr, "adj.P.Val"]
    }
  }
  uniq <- !duplicated(tmp$probe)
  uq <- panel_bh(tmp$PValue[uniq])
  tmp$FDR_panel <- NA_real_
  tmp$FDR_panel[uniq] <- uq
  dup <- which(duplicated(tmp$probe))
  if (length(dup)) {
    tmp$FDR_panel[dup] <- tmp$FDR_panel[match(tmp$probe[dup], tmp$probe)]
  }
  res335[[k]] <- tmp
}
res335 <- do.call(rbind, res335)
write_table(res335, "GSE33505_limma_target_panel.csv")

# GSE90077: RNA-seq counts, edgeR quasi-likelihood with TMM normalization.
count_path <- file.path(data_dir, "GSE90077_JBM_counts.txt.gz")
first <- strsplit(readLines(gzfile(count_path), n = 1), "\t", fixed = TRUE)[[1]][-1]
cts900 <- read.delim(gzfile(count_path), skip = 1, row.names = 1, check.names = FALSE)
stopifnot(ncol(cts900) == length(first))
colnames(cts900) <- first
keep900 <- grepl("^(MeJA|Mock)_", colnames(cts900))
cts900 <- as.matrix(cts900[, keep900, drop = FALSE])
grp900 <- sub("_rep[0-9]+$", "", colnames(cts900))
grp900 <- factor(grp900, levels = c("Mock_1h","MeJA_1h","Mock_5h","MeJA_5h","Mock_8h","MeJA_8h"))
design900 <- model.matrix(~0 + grp900)
colnames(design900) <- levels(grp900)
y900 <- DGEList(counts = cts900)
keepg900 <- filterByExpr(y900, design900)
y900 <- y900[keepg900, , keep.lib.sizes = FALSE]
y900 <- calcNormFactors(y900, method = "TMM")
y900 <- estimateDisp(y900, design900, robust = TRUE)
fit900 <- glmQLFit(y900, design900, robust = TRUE)
cm900 <- makeContrasts(MeJA_1h-Mock_1h, MeJA_5h-Mock_5h, MeJA_8h-Mock_8h, levels = design900)
res900 <- list()
for (k in 1:3) {
  tst <- glmQLFTest(fit900, contrast = cm900[, k])
  tt <- topTags(tst, n = Inf, sort.by = "none")$table
  con <- c("MeJA1h_vs_Mock1h","MeJA5h_vs_Mock5h","MeJA8h_vs_Mock8h")[[k]]
  tmp <- data.frame(dataset="GSE90077", gene=targets$gene, AGI=targets$AGI, contrast=con,
                    log2FC=NA_real_, PValue=NA_real_, FDR_genome=NA_real_, stringsAsFactors=FALSE)
  for (i in seq_len(nrow(tmp))) {
    id <- tmp$AGI[i]
    if (id %in% rownames(tt)) {
      tmp$log2FC[i] <- tt[id, "logFC"]
      tmp$PValue[i] <- tt[id, "PValue"]
      tmp$FDR_genome[i] <- tt[id, "FDR"]
    }
  }
  tmp$FDR_panel <- panel_bh(tmp$PValue)
  res900[[k]] <- tmp
}
res900 <- do.call(rbind, res900)
write_table(res900, "GSE90077_edgeR_target_panel.csv")

# GSE163270: deposited read counts, edgeR 2x2 seedling-JA x adult-JA model.
td <- tempfile("gse163270_")
dir.create(td)
untar(file.path(data_dir, "GSE163270_RAW.tar"), exdir = td)
f163 <- sort(list.files(td, pattern = "\\.csv\\.gz$", full.names = TRUE))
stopifnot(length(f163) == 16)
read163 <- function(f) read.csv(gzfile(f), stringsAsFactors = FALSE)
z0 <- read163(f163[1])
genes163 <- z0$Gene
cts163 <- matrix(0, nrow = length(genes163), ncol = length(f163), dimnames = list(genes163, basename(f163)))
cts163[,1] <- z0$readcounts
for (j in 2:length(f163)) {
  z <- read163(f163[j])
  stopifnot(identical(z$Gene, genes163))
  cts163[,j] <- z$readcounts
}
grp163 <- sub("^GSM[0-9]+_", "", basename(f163))
grp163 <- sub("_rep[0-9]+\\.csv\\.gz$", "", grp163)
seedling <- as.integer(startsWith(grp163, "JA_"))
adult <- as.integer(endsWith(grp163, "_JA"))
design163 <- model.matrix(~ seedling * adult)
y163 <- DGEList(counts = cts163)
keepg163 <- filterByExpr(y163, design163)
y163 <- y163[keepg163, , keep.lib.sizes = FALSE]
y163 <- calcNormFactors(y163, method = "TMM")
y163 <- estimateDisp(y163, design163, robust = TRUE)
fit163 <- glmQLFit(y163, design163, robust = TRUE)
tests163 <- list(acute_JA_unprimed = glmQLFTest(fit163, coef = "adult"),
                 seedlingJA_x_adultJA = glmQLFTest(fit163, coef = "seedling:adult"))
res163 <- list()
for (nm in names(tests163)) {
  tt <- topTags(tests163[[nm]], n = Inf, sort.by = "none")$table
  tmp <- data.frame(dataset="GSE163270", gene=targets$gene, AGI=targets$AGI, contrast=nm,
                    log2FC=NA_real_, PValue=NA_real_, FDR_genome=NA_real_, total_raw_count=NA_real_,
                    stringsAsFactors=FALSE)
  for (i in seq_len(nrow(tmp))) {
    id <- tmp$AGI[i]
    tmp$total_raw_count[i] <- if (id %in% rownames(cts163)) sum(cts163[id, ]) else NA_real_
    if (id %in% rownames(tt)) {
      tmp$log2FC[i] <- tt[id, "logFC"]
      tmp$PValue[i] <- tt[id, "PValue"]
      tmp$FDR_genome[i] <- tt[id, "FDR"]
    }
  }
  tmp$FDR_panel <- panel_bh(tmp$PValue)
  res163[[nm]] <- tmp
}
res163 <- do.call(rbind, res163)
write_table(res163, "GSE163270_edgeR_target_panel.csv")

# GSE180220: normalized Agilent array, collapse uniquely mapped probes to AGI then limma.
x180 <- as.data.frame(read_excel(file.path(data_dir, "GSE180220_Normalized_processed_data.xlsx"),
                                 sheet = "Arabidosis genes"))
colnames(x180)[1:2] <- c("ProbeID","FeatureNo")
expr_cols <- c("c1","c2","c3","p1","p2","p3","m1","m2")
stopifnot(all(expr_cols %in% colnames(x180)))
expr180 <- as.matrix(x180[, expr_cols])
storage.mode(expr180) <- "numeric"
rownames(expr180) <- as.character(x180$FeatureNo)
expr180 <- log2(expr180)
gpl_lines <- readLines(file.path(data_dir, "GPL9020_full.txt"), warn = FALSE)
b <- grep("!platform_table_begin", gpl_lines, fixed = TRUE) + 1
e <- grep("!platform_table_end", gpl_lines, fixed = TRUE) - 1
gpl <- read.delim(text = paste(gpl_lines[b:e], collapse = "\n"), check.names = FALSE,
                  quote = "", stringsAsFactors = FALSE)
extract_agi <- function(s) {
  m <- regmatches(s, gregexpr("AT[1-5]G[0-9]{5}", s, ignore.case = TRUE))[[1]]
  m <- unique(toupper(m))
  if (length(m) == 1) m else NA_character_
}
agi180 <- vapply(gpl$DESCRIPTION, extract_agi, character(1))
map180 <- setNames(agi180, as.character(gpl$ID))
agi_for_row <- unname(map180[rownames(expr180)])
keep180 <- !is.na(agi_for_row) & is.finite(rowSums(expr180))
expr180u <- avereps(expr180[keep180, , drop = FALSE], ID = agi_for_row[keep180])
grp180 <- factor(c("control","control","control","plus","plus","plus","minus","minus"),
                 levels = c("control","plus","minus"))
design180 <- model.matrix(~0 + grp180)
colnames(design180) <- levels(grp180)
fit180 <- eBayes(contrasts.fit(lmFit(expr180u, design180),
                               makeContrasts(plus-control, levels = design180)), robust = TRUE, trend = TRUE)
tt180 <- topTable(fit180, coef = 1, number = Inf, sort.by = "none", adjust.method = "BH")
res180 <- data.frame(dataset="GSE180220", gene=targets$gene, AGI=targets$AGI,
                     contrast="plus_borneol24h_vs_mock24h", log2FC=NA_real_, PValue=NA_real_,
                     FDR_genome=NA_real_, stringsAsFactors=FALSE)
for (i in seq_len(nrow(res180))) {
  id <- res180$AGI[i]
  if (id %in% rownames(tt180)) {
    res180$log2FC[i] <- tt180[id, "logFC"]
    res180$PValue[i] <- tt180[id, "P.Value"]
    res180$FDR_genome[i] <- tt180[id, "adj.P.Val"]
  }
}
res180$FDR_panel <- panel_bh(res180$PValue)
write_table(res180, "GSE180220_limma_target_panel.csv")

# Combined synthesis and audit note.
cols <- c("dataset","gene","AGI","contrast","log2FC","PValue","FDR_panel","FDR_genome")
allres <- rbind(res335[, cols], res900[, cols], res163[, cols], res180[, cols])
write_table(allres, "public_omics_target_panel_bioconductor.csv")

report <- c(
  "# Bioconductor reanalysis audit",
  "",
  "This run replaces the first-pass Welch/OLS significance calculations with standard transcriptomics methods while preserving the prespecified eight-gene target panel.",
  "",
  "- GSE33505: limma empirical-Bayes model on log2 MAS5 ATH1 expression; panel-level and genome-wide BH FDR are both reported.",
  "- GSE90077: edgeR quasi-likelihood negative-binomial model with TMM normalization and whole-transcriptome dispersion estimation; BTH samples excluded from the prespecified MeJA-vs-mock contrasts.",
  "- GSE163270: edgeR quasi-likelihood 2x2 seedling-JA x adult-JA model on deposited read counts; all 16 samples retained.",
  "- GSE180220: limma empirical-Bayes model on log2 normalized Agilent expression after collapsing uniquely mapped probes to AGI loci.",
  "",
  "## Critical interpretation rules",
  "",
  "1. Public datasets are independent external evidence and are not acetophenone-specific measurements.",
  "2. Panel FDR is valid only for the prespecified eight-target family; genome-wide FDR is reported alongside it for transparency.",
  "3. GSE33505 VSP1 and VSP2 remain indistinguishable because both map to ATH1 probe 245928_s_at.",
  "4. Any GSE163270 target removed by count filtering or with zero total raw counts is unavailable, not evidence of no biological response.",
  ""
)
writeLines(report, file.path(out_dir, "BIOCONDUCTOR_REANALYSIS_AUDIT.md"))
cat("Wrote results to", normalizePath(out_dir), "\n")
