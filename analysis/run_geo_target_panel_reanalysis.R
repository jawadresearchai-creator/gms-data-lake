# Compatibility runner for analysis/geo_target_panel_reanalysis.R.
# It applies a narrow parser fix before evaluating the canonical script: read.delim()
# returns a data.frame, so the GEO series-matrix reader must convert it to a numeric
# matrix before setting storage.mode. The scientific/statistical logic is unchanged.

src <- "analysis/geo_target_panel_reanalysis.R"
code <- readLines(src, warn = FALSE)
needle <- '  storage.mode(z) <- "numeric"'
pos <- which(code == needle)
if (length(pos) != 1L) stop("Expected exactly one GEO matrix storage.mode line; found ", length(pos))
code <- append(code, '  z <- as.matrix(z)', after = pos - 1L)
eval(parse(text = code), envir = .GlobalEnv)
