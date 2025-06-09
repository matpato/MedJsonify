# Usability Study Statistical Analysis
# Master's Project - Statistical Validation with P-values

install.packages("tidyverse")
install.packages("psych","car","effsize","corrplot","ggplot2","gridExtra","broom")
# Load required libraries
library(tidyverse)    # Data manipulation and visualization
library(readr)        # Reading CSV files
library(psych)        # Descriptive statistics
library(car)          # ANOVA and statistical tests
library(effsize)      # Effect size calculations
library(corrplot)     # Correlation plots
library(ggplot2)      # Advanced plotting
library(gridExtra)    # Multiple plots
library(broom)        # Tidy statistical output


getwd()
setwd("/Users/matildepato/Data/Clouds/PersonalDrive/ISEL/Mestrados/MESTRADOS-ISEL/ano 2024_25/Filipe Silveira/results")
# ==============================================================================
# 1. DATA LOADING AND PREPROCESSING
# ==============================================================================

# Read the CSV file
data <- read_csv("Usability_responses_homon.csv", 
                 locale = locale(encoding = "UTF-8"),
                 show_col_types = FALSE)

# Display basic information about the dataset
cat("Dataset Overview:\n")
cat("Number of participants:", nrow(data), "\n")
cat("Number of variables:", ncol(data), "\n\n")

# Clean column names for easier analysis
# Extract key variables with cleaner names
usability_data <- data %>%
  select(
    # Demographics
    gender = Género,
    age = Idade,
    education = Escolaridade,
    tech_affinity = `Afinidade Tecnológica`,
    
    # Interest scenarios (convert to numeric scale)
    interest_automation = contains("Adicionar dispositivos inteligentes"),
    interest_management = contains("Gerir todos os dispositivos"),
    interest_sensors = contains("Instalar sensores"),
    interest_monitoring = contains("monitoriza a atividade"),
    
    # Task difficulty ratings
    task_difficulty_1 = contains("Para si, o quão fácil foi completar esta tarefa?"),
    
    # SUS and usability items
    contains("gostaria de utilizar"),
    contains("desnecessariamente complexo"),
    contains("fácil de usar"),
    contains("conhecimentos técnicos"),
    contains("bem integrada"),
    contains("inconsistências"),
    contains("aprenderia a usar"),
    contains("complicado de usar"),
    contains("confiante ao usar"),
    contains("aprender muitas coisas"),
    
    # Website usability
    contains("website"),
    
    # NPS
    nps = contains("probabilidade de recomendar")
  )

# Convert interest levels to numeric scales (1-5)
interest_mapping <- c("Nada interessado" = 1, "Pouco Interessado" = 2, 
                      "Interessado" = 3, "Muito Interessado" = 4)

# Apply conversions where needed
# Note: Adjust these conversions based on your specific scale

# ==============================================================================
# 2. DESCRIPTIVE STATISTICS
# ==============================================================================

# Demographic summary
cat("DEMOGRAPHIC SUMMARY:\n")
cat("==================\n\n")

# Gender distribution
gender_summary <- table(usability_data$gender)
cat("Gender Distribution:\n")
print(gender_summary)
cat("\n")

# Age distribution
age_summary <- table(usability_data$age)
cat("Age Distribution:\n")
print(age_summary)
cat("\n")

# Education distribution
education_summary <- table(usability_data$education)
cat("Education Distribution:\n")
print(education_summary)
cat("\n")

# Tech affinity distribution
tech_summary <- table(usability_data$tech_affinity)
cat("Tech Affinity Distribution:\n")
print(tech_summary)
cat("\n")

# ==============================================================================
# 3. STATISTICAL TESTS AND P-VALUES
# ==============================================================================

# Create a results data frame to store all p-values
results_df <- data.frame(
  Test = character(),
  Variable = character(),
  Statistic = numeric(),
  P_Value = numeric(),
  Effect_Size = numeric(),
  Interpretation = character(),
  stringsAsFactors = FALSE
)

# Function to add results to our summary table
add_result <- function(test_name, variable, statistic, p_value, effect_size = NA, interpretation = "") {
  results_df <<- rbind(results_df, data.frame(
    Test = test_name,
    Variable = variable,
    Statistic = statistic,
    P_Value = p_value,
    Effect_Size = effect_size,
    Interpretation = interpretation
  ))
}

# ==============================================================================
# 3.1 ONE-SAMPLE TESTS (Testing against theoretical means)
# ==============================================================================

# Test if task difficulty significantly differs from neutral (3.0 on 1-5 scale)
# Extract numeric task difficulty values
task_diff_numeric <- as.numeric(usability_data$task_difficulty_11)
task_diff_clean <- task_diff_numeric[!is.na(task_diff_numeric)]

if(length(task_diff_clean) > 0) {
  # One-sample t-test against neutral score of 3
  t_test_task <- t.test(task_diff_clean, mu = 3)
  
  add_result("One-sample t-test", "Task Difficulty vs Neutral(3)", 
             t_test_task$statistic, t_test_task$p.value,
             abs(mean(task_diff_clean) - 3) / sd(task_diff_clean),
             ifelse(t_test_task$p.value < 0.05, "Significantly different from neutral", "Not significantly different"))
  
  cat("Task Difficulty Analysis:\n")
  cat("Mean task difficulty:", round(mean(task_diff_clean), 2), "\n")
  cat("t-statistic:", round(t_test_task$statistic, 3), "\n")
  cat("p-value:", format(t_test_task$p.value, scientific = TRUE), "\n\n")
}

# ==============================================================================
# 3.2 GROUP COMPARISONS (Independent samples)
# ==============================================================================

# Compare task difficulty by gender
if(length(unique(usability_data$gender)) >= 2) {
  # ANOVA for task difficulty by gender
  gender_groups <- split(task_diff_clean, usability_data$gender[!is.na(task_diff_numeric)])
  
  if(length(gender_groups) >= 2 && all(sapply(gender_groups, length) > 0)) {
    anova_gender <- aov(task_diff_clean ~ usability_data$gender[!is.na(task_diff_numeric)])
    anova_summary <- summary(anova_gender)
    p_val_gender <- anova_summary[[1]][["Pr(>F)"]][1]
    f_stat <- anova_summary[[1]][["F value"]][1]
    
    add_result("One-way ANOVA", "Task Difficulty by Gender", 
               f_stat, p_val_gender, NA,
               ifelse(p_val_gender < 0.05, "Significant gender differences", "No significant gender differences"))
  }
}

# Compare task difficulty by tech affinity
tech_affinity_clean <- usability_data$tech_affinity[!is.na(task_diff_numeric)]
if(length(unique(tech_affinity_clean)) >= 2) {
  anova_tech <- aov(task_diff_clean ~ tech_affinity_clean)
  anova_tech_summary <- summary(anova_tech)
  p_val_tech <- anova_tech_summary[[1]][["Pr(>F)"]][1]
  f_stat_tech <- anova_tech_summary[[1]][["F value"]][1]
  
  add_result("One-way ANOVA", "Task Difficulty by Tech Affinity", 
             f_stat_tech, p_val_tech, NA,
             ifelse(p_val_tech < 0.05, "Significant tech affinity differences", "No significant tech affinity differences"))
}

# ==============================================================================
# 3.3 CORRELATION ANALYSES
# ==============================================================================

# Extract all numeric columns for correlation analysis
numeric_cols <- usability_data %>% 
  select_if(is.numeric) %>%
  select(-contains("Timestamp"))

if(ncol(numeric_cols) >= 2) {
  # Correlation matrix
  cor_matrix <- cor(numeric_cols, use = "complete.obs")
  
  cat("CORRELATION ANALYSIS:\n")
  cat("===================\n")
  print(round(cor_matrix, 3))
  cat("\n")
  
  # Test correlations for significance using cor.test() for each pair
  var_names <- colnames(numeric_cols)
  
  for(i in 1:(length(var_names)-1)) {
    for(j in (i+1):length(var_names)) {
      var1 <- var_names[i]
      var2 <- var_names[j]
      
      # Get complete cases for both variables
      complete_cases <- complete.cases(numeric_cols[, c(var1, var2)])
      
      if(sum(complete_cases) >= 3) {  # Need at least 3 observations
        cor_test <- cor.test(numeric_cols[[var1]][complete_cases], 
                             numeric_cols[[var2]][complete_cases],
                             method = "pearson")
        
        add_result("Pearson Correlation", paste(var1, "vs", var2),
                   cor_test$estimate, cor_test$p.value, abs(cor_test$estimate),
                   ifelse(cor_test$p.value < 0.01, "Highly significant correlation", 
                          ifelse(cor_test$p.value < 0.05, "Significant correlation", "Not significant")))
      }
    }
  }
}

# ==============================================================================
# 3.4 NON-PARAMETRIC TESTS
# ==============================================================================

# Wilcoxon signed-rank test (non-parametric alternative to one-sample t-test)
if(length(task_diff_clean) > 0) {
  wilcox_test <- wilcox.test(task_diff_clean, mu = 3)
  
  add_result("Wilcoxon signed-rank", "Task Difficulty vs Neutral(3)", 
             wilcox_test$statistic, wilcox_test$p.value, NA,
             ifelse(wilcox_test$p.value < 0.05, "Significantly different (non-parametric)", "Not significantly different"))
}

# Mann-Whitney U test for gender differences (non-parametric alternative to t-test)
if(length(unique(usability_data$gender)) == 2) {
  gender_levels <- unique(usability_data$gender)
  gender_levels <- gender_levels[!is.na(gender_levels)]
  
  if(length(gender_levels) == 2) {
    group1 <- task_diff_clean[usability_data$gender[!is.na(task_diff_numeric)] == gender_levels[1]]
    group2 <- task_diff_clean[usability_data$gender[!is.na(task_diff_numeric)] == gender_levels[2]]
    
    if(length(group1) > 0 && length(group2) > 0) {
      mann_whitney <- wilcox.test(group1, group2)
      
      add_result("Mann-Whitney U", paste("Task Difficulty:", gender_levels[1], "vs", gender_levels[2]),
                 mann_whitney$statistic, mann_whitney$p.value, NA,
                 ifelse(mann_whitney$p.value < 0.05, "Significant gender difference (non-parametric)", "No significant difference"))
    }
  }
}

# ==============================================================================
# 3.5 CHI-SQUARE TESTS FOR CATEGORICAL VARIABLES
# ==============================================================================

# Chi-square test for independence between categorical variables
# Gender vs Tech Affinity
if(length(unique(usability_data$gender)) >= 2 && length(unique(usability_data$tech_affinity)) >= 2) {
  contingency_table <- table(usability_data$gender, usability_data$tech_affinity)
  
  if(all(contingency_table >= 5)) {  # Check expected frequencies
    chi_sq_test <- chisq.test(contingency_table)
    
    add_result("Chi-square test", "Gender vs Tech Affinity Independence",
               chi_sq_test$statistic, chi_sq_test$p.value, 
               sqrt(chi_sq_test$statistic / sum(contingency_table)),  # Cramér's V
               ifelse(chi_sq_test$p.value < 0.05, "Variables are dependent", "Variables are independent"))
  }
}

# ==============================================================================
# 3.6 NORMALITY TESTS
# ==============================================================================

# Shapiro-Wilk test for normality of task difficulty scores
if(length(task_diff_clean) > 3 && length(task_diff_clean) < 5000) {
  shapiro_test <- shapiro.test(task_diff_clean)
  
  add_result("Shapiro-Wilk", "Task Difficulty Normality",
             shapiro_test$statistic, shapiro_test$p.value, NA,
             ifelse(shapiro_test$p.value < 0.05, "Data not normally distributed", "Data appears normally distributed"))
}

# ==============================================================================
# 4. RESULTS SUMMARY
# ==============================================================================

cat("\n", paste(rep("=", 80), collapse=""), "\n")
cat("STATISTICAL ANALYSIS RESULTS SUMMARY\n")
cat(paste(rep("=", 80), collapse=""), "\n\n")

# Sort results by p-value
results_df <- results_df[order(results_df$P_Value), ]

# Print formatted results table
cat("All Statistical Tests (sorted by p-value):\n")
cat(paste(rep("-", 50), collapse=""), "\n")

for(i in 1:nrow(results_df)) {
  cat(sprintf("%-25s | %-30s\n", results_df$Test[i], results_df$Variable[i]))
  cat(sprintf("Statistic: %8.3f | p-value: %s\n", 
              results_df$Statistic[i], 
              ifelse(results_df$P_Value[i] < 0.001, "< 0.001", sprintf("%.4f", results_df$P_Value[i]))))
  if(!is.na(results_df$Effect_Size[i])) {
    cat(sprintf("Effect Size: %7.3f | %s\n", results_df$Effect_Size[i], results_df$Interpretation[i]))
  } else {
    cat(sprintf("                   | %s\n", results_df$Interpretation[i]))
  }
  cat(sprintf("Significance: %s\n", ifelse(results_df$P_Value[i] < 0.05, "**SIGNIFICANT**", "Not significant")))
  cat(paste(rep("-", 50), collapse=""), "\n")
}

# Summary of significant results
significant_results <- results_df[results_df$P_Value < 0.05, ]

cat("\nSIGNIFICANT FINDINGS (p < 0.05):\n")
cat("================================\n")

if(nrow(significant_results) > 0) {
  for(i in 1:nrow(significant_results)) {
    cat(sprintf("%d. %s - %s (p = %.4f)\n", 
                i, significant_results$Test[i], 
                significant_results$Variable[i], 
                significant_results$P_Value[i]))
    cat(sprintf("   %s\n\n", significant_results$Interpretation[i]))
  }
} else {
  cat("No statistically significant results found at α = 0.05 level.\n")
}

# Effect size interpretation
cat("EFFECT SIZE INTERPRETATION:\n")
cat("===========================\n")
cat("Small effect: 0.1 - 0.3\n")
cat("Medium effect: 0.3 - 0.5\n")
cat("Large effect: > 0.5\n\n")


# ==============================================================================
# 6. POWER ANALYSIS
# ==============================================================================
# Add this at the beginning:
if (!require(pwr)) {
  install.packages("pwr")
  library(pwr)
}
pwr_available <- require(pwr)

# Only run power analysis if pwr package is available
if(pwr_available) {
  
  cat("\n", paste(rep("=", 80), collapse=""), "\n")
  cat("POWER ANALYSIS - SAMPLE SIZE ADEQUACY\n")
  cat(paste(rep("=", 80), collapse=""), "\n\n")
  
  # Current sample size
  n_current <- nrow(data)
  cat("Current sample size:", n_current, "participants\n\n")
  
  # Create power analysis results dataframe
  power_results <- data.frame(
    Test_Type = character(),
    Effect_Size = character(),
    Current_Power = numeric(),
    Required_N = numeric(),
    Adequate = character(),
    stringsAsFactors = FALSE
  )
  
  # Function to add power results
  add_power_result <- function(test_type, effect_size, current_power, required_n, adequate) {
    power_results <<- rbind(power_results, data.frame(
      Test_Type = test_type,
      Effect_Size = effect_size,
      Current_Power = current_power,
      Required_N = required_n,
      Adequate = adequate
    ))
  }
  
  cat("POWER ANALYSIS FOR DIFFERENT EFFECT SIZES:\n")
  cat("==========================================\n\n")
  
  # Define effect size conventions
  # Cohen's conventions: small = 0.2, medium = 0.5, large = 0.8
  
  # ==============================================================================
  # 6.1 ONE-SAMPLE T-TEST POWER ANALYSIS
  # ==============================================================================
  
  cat("1. ONE-SAMPLE T-TEST (Task Difficulty vs Neutral):\n")
  cat(paste(rep("-", 50), collapse=""), "\n")
  
  # Calculate power for different effect sizes
  effect_sizes_t <- c(0.2, 0.5, 0.8)  # Small, medium, large
  effect_labels <- c("Small (d=0.2)", "Medium (d=0.5)", "Large (d=0.8)")
  
  for(i in 1:length(effect_sizes_t)) {
    # Current power with n=55
    current_power <- pwr.t.test(n = n_current, d = effect_sizes_t[i], 
                                sig.level = 0.05, type = "one.sample")$power
    
    # Required sample size for 80% power
    required_n <- ceiling(pwr.t.test(d = effect_sizes_t[i], power = 0.8, 
                                     sig.level = 0.05, type = "one.sample")$n)
    
    adequate <- ifelse(current_power >= 0.8, "YES", "NO")
    
    cat(sprintf("%-15s: Power = %.3f, Required N = %3d, Adequate = %s\n", 
                effect_labels[i], current_power, required_n, adequate))
    
    add_power_result("One-sample t-test", effect_labels[i], 
                     current_power, required_n, adequate)
  }
  
  cat("\n")
  
  # ==============================================================================
  # 6.2 TWO-SAMPLE T-TEST POWER ANALYSIS (Gender Comparison)
  # ==============================================================================
  
  cat("2. TWO-SAMPLE T-TEST (Gender Comparison):\n")
  cat(paste(rep("-", 50), collapse=""), "\n")
  
  # Assume roughly equal group sizes (conservative estimate)
  n_per_group <- n_current / 2
  
  for(i in 1:length(effect_sizes_t)) {
    # Current power with current sample
    current_power <- pwr.t.test(n = n_per_group, d = effect_sizes_t[i], 
                                sig.level = 0.05, type = "two.sample")$power
    
    # Required sample size per group for 80% power
    required_n_per_group <- ceiling(pwr.t.test(d = effect_sizes_t[i], power = 0.8, 
                                               sig.level = 0.05, type = "two.sample")$n)
    
    adequate <- ifelse(current_power >= 0.8, "YES", "NO")
    
    cat(sprintf("%-15s: Power = %.3f, Required N per group = %3d, Adequate = %s\n", 
                effect_labels[i], current_power, required_n_per_group, adequate))
    
    add_power_result("Two-sample t-test", effect_labels[i], 
                     current_power, required_n_per_group * 2, adequate)
  }
  
  cat("\n")
  
  # ==============================================================================
  # 6.3 ANOVA POWER ANALYSIS (Multiple Groups)
  # ==============================================================================
  
  cat("3. ONE-WAY ANOVA (Tech Affinity Groups):\n")
  cat(paste(rep("-", 50), collapse=""), "\n")
  
  # Estimate number of groups (assuming 3-4 tech affinity levels)
  k_groups <- 4  # Number of groups
  effect_sizes_f <- c(0.1, 0.25, 0.4)  # Small, medium, large for ANOVA
  effect_labels_f <- c("Small (f=0.1)", "Medium (f=0.25)", "Large (f=0.4)")
  
  for(i in 1:length(effect_sizes_f)) {
    # Current power
    current_power <- pwr.anova.test(k = k_groups, n = n_current/k_groups, 
                                    f = effect_sizes_f[i], sig.level = 0.05)$power
    
    # Required sample size per group for 80% power
    required_n_per_group <- ceiling(pwr.anova.test(k = k_groups, f = effect_sizes_f[i], 
                                                   power = 0.8, sig.level = 0.05)$n)
    
    adequate <- ifelse(current_power >= 0.8, "YES", "NO")
    
    cat(sprintf("%-17s: Power = %.3f, Required N per group = %3d, Adequate = %s\n", 
                effect_labels_f[i], current_power, required_n_per_group, adequate))
    
    add_power_result("One-way ANOVA", effect_labels_f[i], 
                     current_power, required_n_per_group * k_groups, adequate)
  }
  
  cat("\n")
  
  # ==============================================================================
  # 6.4 CORRELATION POWER ANALYSIS
  # ==============================================================================
  
  cat("4. CORRELATION ANALYSIS:\n")
  cat(paste(rep("-", 50), collapse=""), "\n")
  
  effect_sizes_r <- c(0.1, 0.3, 0.5)  # Small, medium, large correlations
  effect_labels_r <- c("Small (r=0.1)", "Medium (r=0.3)", "Large (r=0.5)")
  
  for(i in 1:length(effect_sizes_r)) {
    # Current power
    current_power <- pwr.r.test(n = n_current, r = effect_sizes_r[i], 
                                sig.level = 0.05)$power
    
    # Required sample size for 80% power
    required_n <- ceiling(pwr.r.test(r = effect_sizes_r[i], power = 0.8, 
                                     sig.level = 0.05)$n)
    
    adequate <- ifelse(current_power >= 0.8, "YES", "NO")
    
    cat(sprintf("%-15s: Power = %.3f, Required N = %3d, Adequate = %s\n", 
                effect_labels_r[i], current_power, required_n, adequate))
    
    add_power_result("Correlation", effect_labels_r[i], 
                     current_power, required_n, adequate)
  }
  
  cat("\n")
  
  # ==============================================================================
  # 6.5 CHI-SQUARE POWER ANALYSIS
  # ==============================================================================
  
  cat("5. CHI-SQUARE TEST (Categorical Associations):\n")
  cat(paste(rep("-", 50), collapse=""), "\n")
  
  # For 2x2 contingency table
  effect_sizes_w <- c(0.1, 0.3, 0.5)  # Small, medium, large
  effect_labels_w <- c("Small (w=0.1)", "Medium (w=0.3)", "Large (w=0.5)")
  
  for(i in 1:length(effect_sizes_w)) {
    # Current power
    current_power <- pwr.chisq.test(w = effect_sizes_w[i], N = n_current, 
                                    df = 1, sig.level = 0.05)$power
    
    # Required sample size for 80% power
    required_n <- ceiling(pwr.chisq.test(w = effect_sizes_w[i], power = 0.8, 
                                         df = 1, sig.level = 0.05)$N)
    
    adequate <- ifelse(current_power >= 0.8, "YES", "NO")
    
    cat(sprintf("%-17s: Power = %.3f, Required N = %3d, Adequate = %s\n", 
                effect_labels_w[i], current_power, required_n, adequate))
    
    add_power_result("Chi-square test", effect_labels_w[i], 
                     current_power, required_n, adequate)
  }
  
  cat("\n")
  
  # ==============================================================================
  # 6.6 POWER ANALYSIS SUMMARY
  # ==============================================================================
  
  cat("POWER ANALYSIS SUMMARY:\n")
  cat("=======================\n\n")
  
  # Count adequate vs inadequate power
  adequate_count <- sum(power_results$Adequate == "YES")
  total_tests <- nrow(power_results)
  inadequate_count <- total_tests - adequate_count
  
  cat(sprintf("Tests with adequate power (≥80%%): %d out of %d (%.1f%%)\n", 
              adequate_count, total_tests, (adequate_count/total_tests)*100))
  cat(sprintf("Tests with inadequate power (<80%%): %d out of %d (%.1f%%)\n\n", 
              inadequate_count, total_tests, (inadequate_count/total_tests)*100))
  
  # Show which effect sizes are adequately powered
  adequate_tests <- power_results[power_results$Adequate == "YES", ]
  if(nrow(adequate_tests) > 0) {
    cat("ADEQUATELY POWERED TESTS:\n")
    for(i in 1:nrow(adequate_tests)) {
      cat(sprintf("- %s (%s): Power = %.3f\n", 
                  adequate_tests$Test_Type[i], adequate_tests$Effect_Size[i], 
                  adequate_tests$Current_Power[i]))
    }
    cat("\n")
  }
  
  # Show which tests need more participants
  inadequate_tests <- power_results[power_results$Adequate == "NO", ]
  if(nrow(inadequate_tests) > 0) {
    cat("TESTS NEEDING MORE PARTICIPANTS:\n")
    for(i in 1:nrow(inadequate_tests)) {
      additional_needed <- inadequate_tests$Required_N[i] - n_current
      cat(sprintf("- %s (%s): Need %d more participants (Total: %d)\n", 
                  inadequate_tests$Test_Type[i], inadequate_tests$Effect_Size[i], 
                  additional_needed, inadequate_tests$Required_N[i]))
    }
    cat("\n")
  }
  # ==============================================================================
  # 6.7 PRACTICAL RECOMMENDATIONS
  # ==============================================================================
  
  cat("PRACTICAL RECOMMENDATIONS:\n")
  cat("==========================\n")
  
  # Overall assessment
  large_effect_adequate <- sum(power_results$Adequate == "YES" & 
                                 grepl("Large", power_results$Effect_Size))
  medium_effect_adequate <- sum(power_results$Adequate == "YES" & 
                                  grepl("Medium", power_results$Effect_Size))
  small_effect_adequate <- sum(power_results$Adequate == "YES" & 
                                 grepl("Small", power_results$Effect_Size))
  
  cat(sprintf("✓ Your sample (n=%d) is adequate for detecting:\n", n_current))
  if(large_effect_adequate > 0) cat("  - Large effects in most tests\n")
  if(medium_effect_adequate > 0) cat("  - Medium effects in some tests\n")
  if(small_effect_adequate > 0) cat("  - Small effects in few tests\n")
  
  cat("\n")
  
  # Find the minimum additional sample needed
  min_additional <- min(inadequate_tests$Required_N) - n_current
  if(length(min_additional) > 0 && min_additional > 0) {
    cat(sprintf("⚠ To detect medium effects reliably, consider collecting %d more responses\n", 
                min_additional))
    cat(sprintf("⚠ For maximum power across all tests, aim for %d total participants\n", 
                max(inadequate_tests$Required_N)))
  } else {
    cat("✓ Your current sample size appears adequate for most effect sizes of interest\n")
  }
  
  cat("\n")
  cat("EFFECT SIZE GUIDELINES:\n")
  cat("- Small effects: Theoretical interest, may not be practically meaningful\n")
  cat("- Medium effects: Typical for usability studies, practically meaningful\n") 
  cat("- Large effects: Strong practical significance, easy to detect\n\n")
  
  cat("CONCLUSION:\n")
  if(medium_effect_adequate >= 3) {
    cat("✓ Your sample size is generally adequate for a usability study\n")
    cat("✓ You can reliably detect medium to large effects\n")
  } else {
    cat("⚠ Consider collecting more data to improve power for medium effects\n")
    cat("✓ Current sample is sufficient for detecting large effects\n")
  }
  
  # Export power analysis results
  write.csv(power_results, "power_analysis_results.csv", row.names = FALSE)
  cat("\nPower analysis results exported to 'power_analysis_results.csv'\n")
  
} else {
  cat("\n", paste(rep("=", 80), collapse=""), "\n")
  cat("POWER ANALYSIS - SKIPPED\n")
  cat(paste(rep("=", 80), collapse=""), "\n")
  cat("⚠ Power analysis skipped due to missing 'pwr' package.\n")
  cat("To install manually, run: install.packages('pwr')\n\n")
  
  # Provide basic power guidelines without calculations
  cat("BASIC POWER GUIDELINES FOR n=55:\n")
  cat("================================\n")
  cat("✓ Generally adequate for usability studies\n")
  cat("✓ Good power for large effects (Cohen's d ≥ 0.8)\n")
  cat("⚠ Moderate power for medium effects (Cohen's d ≥ 0.5)\n")
  cat("⚠ Limited power for small effects (Cohen's d ≥ 0.2)\n\n")
  cat("Recommendation: Your sample size should be sufficient for detecting\n")
  cat("meaningful differences in a usability study context.\n\n")
}

cat("\nPower analysis results exported to 'power_analysis_results.csv'\n")

# Export results to CSV
write.csv(results_df, "statistical_results.csv", row.names = FALSE)
cat("Results exported to 'statistical_results.csv'\n")

# ==============================================================================
# 5. ADDITIONAL RECOMMENDATIONS
# ==============================================================================

cat("RECOMMENDATIONS FOR FURTHER ANALYSIS:\n")
cat("====================================\n")
cat("1. Consider power analysis to determine if sample size is adequate\n")
cat("2. Apply Bonferroni correction for multiple comparisons if needed\n")
cat("3. Examine effect sizes alongside p-values for practical significance\n")
cat("4. Consider non-parametric alternatives if normality assumptions are violated\n")
cat("5. Visualize your data with boxplots, histograms, and scatterplots\n")
cat("6. Calculate confidence intervals for your main findings\n\n")



cat("\nAnalysis complete! Remember to interpret p-values in context with effect sizes and practical significance.\n")