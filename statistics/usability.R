# Usability Research Statistical Analysis
# Load required libraries
library(readr)
library(dplyr)
library(ggplot2)
library(tidyr)
library(car)
library(psych)
library(corrplot)
library(gridExtra)
library(RColorBrewer)
library(knitr)

# Set theme for plots
theme_set(theme_minimal() + 
            theme(plot.title = element_text(hjust = 0.5, size = 14, face = "bold"),
                  axis.text = element_text(size = 10),
                  legend.text = element_text(size = 9)))

#============================================================================
# 1. DATA LOADING AND CLEANING
#============================================================================

# Load the data
data <- read_csv("Usability_responses_homon.csv", locale = locale(encoding = "UTF-8"))

# Clean column names for easier handling
colnames(data) <- c(
  "Timestamp", "Gender", "Age", "Education", "Tech_Affinity",
  "Interest_Automation", "Interest_Management", "Interest_Sensors", "Interest_Monitoring",
  "Task1_Ease", "Task1_Difficulty", "Task1_Suggestions",
  "Task2_Ease", "Task2_Difficulty", "Task2_Suggestions", 
  "Task3_Ease", "Task3_Difficulty", "Task3_Suggestions",
  "SUS1_Frequency", "SUS2_Complex", "SUS3_Easy", "SUS4_Support",
  "SUS5_Integrated", "SUS6_Inconsistent", "SUS7_Quick_Learn", "SUS8_Complicated",
  "SUS9_Confident", "SUS10_Learn_Much", "Website_Find", "Website_Navigate",
  "Website_Easy", "Website_Trust", "Website_Clean", "NPS_Score"
)

# Convert categorical variables to factors with proper levels
data <- data %>%
  mutate(
    Gender = factor(Gender, levels = c("Masculino", "Feminino", "Outro")),
    Age = factor(Age, levels = c("18 - 25 anos", "26 - 35 anos", "36 - 45 anos", 
                                 "46 - 55 anos", "56 - 65 anos", "Mais de 65 anos")),
    Education = factor(Education, levels = c("Ensino Básico", "Ensino Secundário", 
                                             "Licenciatura", "Mestrado", "Doutoramento")),
    Tech_Affinity = factor(Tech_Affinity, levels = c("Muito Baixa", "Baixa", "Normal", 
                                                     "Alta", "Muito Alta")),
    # Convert interest levels to numeric scale
    across(starts_with("Interest_"), ~case_when(
      . == "Nada interessado" ~ 1,
      . == "Pouco Interessado" ~ 2,
      . == "Interessado" ~ 3,
      . == "Muito Interessado" ~ 4,
      TRUE ~ as.numeric(.)
    )),
    # Ensure numeric variables are properly converted
    across(c(starts_with("Task"), starts_with("SUS"), starts_with("Website"), "NPS_Score"), as.numeric)
  )

#============================================================================
# 2. CALCULATE SUS SCORES
#============================================================================

# Calculate SUS scores (Standard method: odd items -1, even items 5-, then *2.5)
data <- data %>%
  mutate(
    SUS_Score = ((SUS1_Frequency - 1) + (5 - SUS2_Complex) + (SUS3_Easy - 1) + 
                   (5 - SUS4_Support) + (SUS5_Integrated - 1) + (5 - SUS6_Inconsistent) + 
                   (SUS7_Quick_Learn - 1) + (5 - SUS8_Complicated) + (SUS9_Confident - 1) + 
                   (5 - SUS10_Learn_Much)) * 2.5,
    
    # Create SUS interpretation categories
    SUS_Category = case_when(
      SUS_Score >= 80.3 ~ "Excellent",
      SUS_Score >= 68 ~ "Good", 
      SUS_Score >= 51 ~ "OK",
      SUS_Score >= 25.1 ~ "Poor",
      TRUE ~ "Awful"
    ),
    SUS_Category = factor(SUS_Category, levels = c("Awful", "Poor", "OK", "Good", "Excellent"))
  )

#============================================================================
# 3. DESCRIPTIVE STATISTICS
#============================================================================

print("=== DESCRIPTIVE STATISTICS ===")
print("Sample Demographics:")
print(table(data$Gender))
print(table(data$Age))
print(table(data$Education))
print(table(data$Tech_Affinity))

print("\nSUS Score Summary:")
print(summary(data$SUS_Score))
print(paste("Mean SUS Score:", round(mean(data$SUS_Score, na.rm = TRUE), 2)))
print(paste("SD SUS Score:", round(sd(data$SUS_Score, na.rm = TRUE), 2)))

print("\nSUS Categories:")
print(table(data$SUS_Category))

#============================================================================
# 4. GROUP COMPARISON ANALYSES
#============================================================================

print("\n=== GROUP COMPARISONS ===")

# Function to perform group comparison tests
perform_group_tests <- function(dependent_var, grouping_var, var_name, group_name) {
  cat("\n", paste("Comparing", var_name, "by", group_name), "\n")
  cat(paste(rep("=", 50), collapse = ""), "\n")
  
  # Remove NA values
  clean_data <- data[!is.na(data[[dependent_var]]) & !is.na(data[[grouping_var]]), ]
  
  # Descriptive statistics by group
  desc_stats <- clean_data %>%
    group_by(!!sym(grouping_var)) %>%
    summarise(
      n = n(),
      mean = round(mean(!!sym(dependent_var), na.rm = TRUE), 2),
      sd = round(sd(!!sym(dependent_var), na.rm = TRUE), 2),
      median = median(!!sym(dependent_var), na.rm = TRUE),
      .groups = 'drop'
    )
  print(desc_stats)
  
  # Test for normality (Shapiro-Wilk for each group)
  groups <- unique(clean_data[[grouping_var]])
  normality_tests <- sapply(groups, function(g) {
    group_data <- clean_data[clean_data[[grouping_var]] == g, dependent_var]
    if(length(group_data) >= 3 && length(group_data) <= 5000) {
      shapiro.test(group_data)$p.value
    } else NA
  })
  
  cat("\nNormality Tests (Shapiro-Wilk p-values):\n")
  print(round(normality_tests, 4))
  
  # Levene's test for homogeneity of variance
  if(length(groups) >= 2) {
    levene_result <- leveneTest(as.formula(paste(dependent_var, "~", grouping_var)), 
                                data = clean_data)
    cat("\nLevene's Test for Equal Variances:\n")
    cat("F =", round(levene_result$`F value`[1], 4), 
        ", p =", round(levene_result$`Pr(>F)`[1], 4), "\n")
    
    # Choose appropriate test based on assumptions
    if(length(groups) == 2) {
      # Two-group comparison
      if(all(normality_tests > 0.05, na.rm = TRUE) && levene_result$`Pr(>F)`[1] > 0.05) {
        # t-test (equal variances)
        test_result <- t.test(as.formula(paste(dependent_var, "~", grouping_var)), 
                              data = clean_data, var.equal = TRUE)
        cat("\nIndependent t-test (equal variances):\n")
        cat("t =", round(test_result$statistic, 4), 
            ", df =", test_result$parameter,
            ", p =", round(test_result$p.value, 4), "\n")
        cat("Cohen's d =", round(abs(diff(desc_stats$mean)) / 
                                   sqrt(mean(desc_stats$sd^2)), 2), "\n")
      } else if(all(normality_tests > 0.05, na.rm = TRUE)) {
        # Welch's t-test (unequal variances)
        test_result <- t.test(as.formula(paste(dependent_var, "~", grouping_var)), 
                              data = clean_data, var.equal = FALSE)
        cat("\nWelch's t-test (unequal variances):\n")
        cat("t =", round(test_result$statistic, 4), 
            ", df =", round(test_result$parameter, 2),
            ", p =", round(test_result$p.value, 4), "\n")
      } else {
        # Mann-Whitney U test
        test_result <- wilcox.test(as.formula(paste(dependent_var, "~", grouping_var)), 
                                   data = clean_data)
        cat("\nMann-Whitney U test:\n")
        cat("W =", test_result$statistic, 
            ", p =", round(test_result$p.value, 4), "\n")
      }
    } else {
      # Multiple group comparison
      if(all(normality_tests > 0.05, na.rm = TRUE) && levene_result$`Pr(>F)`[1] > 0.05) {
        # ANOVA
        anova_result <- aov(as.formula(paste(dependent_var, "~", grouping_var)), 
                            data = clean_data)
        anova_summary <- summary(anova_result)
        cat("\nOne-way ANOVA:\n")
        cat("F =", round(anova_summary[[1]]$`F value`[1], 4),
            ", df =", anova_summary[[1]]$Df[1], ",", anova_summary[[1]]$Df[2],
            ", p =", round(anova_summary[[1]]$`Pr(>F)`[1], 4), "\n")
        
        # Post-hoc tests if significant
        if(anova_summary[[1]]$`Pr(>F)`[1] < 0.05) {
          tukey_result <- TukeyHSD(anova_result)
          cat("\nTukey HSD Post-hoc Test:\n")
          print(round(tukey_result[[1]], 4))
        }
      } else {
        # Kruskal-Wallis test
        kw_result <- kruskal.test(as.formula(paste(dependent_var, "~", grouping_var)), 
                                  data = clean_data)
        cat("\nKruskal-Wallis test:\n")
        cat("Chi-squared =", round(kw_result$statistic, 4),
            ", df =", kw_result$parameter,
            ", p =", round(kw_result$p.value, 4), "\n")
        
        # Post-hoc tests if significant
        if(kw_result$p.value < 0.05) {
          cat("\nPairwise comparisons needed (Dunn's test recommended)\n")
        }
      }
    }
  }
  
  return(desc_stats)
}

# Perform group comparisons
sus_by_gender <- perform_group_tests("SUS_Score", "Gender", "SUS Score", "Gender")
sus_by_age <- perform_group_tests("SUS_Score", "Age", "SUS Score", "Age")
sus_by_education <- perform_group_tests("SUS_Score", "Education", "SUS Score", "Education")  
sus_by_tech <- perform_group_tests("SUS_Score", "Tech_Affinity", "SUS Score", "Tech Affinity")

# Task completion comparisons
task1_by_tech <- perform_group_tests("Task1_Ease", "Tech_Affinity", "Task 1 Ease", "Tech Affinity")
task2_by_tech <- perform_group_tests("Task2_Ease", "Tech_Affinity", "Task 2 Ease", "Tech Affinity")
task3_by_tech <- perform_group_tests("Task3_Ease", "Tech_Affinity", "Task 3 Ease", "Tech Affinity")

#============================================================================
# 5. CORRELATION ANALYSIS
#============================================================================

print("\n=== CORRELATION ANALYSIS ===")

# Select numeric variables for correlation
numeric_vars <- data %>%
  select(Interest_Automation, Interest_Management, Interest_Sensors, Interest_Monitoring,
         Task1_Ease, Task2_Ease, Task3_Ease, SUS_Score, 
         Website_Find, Website_Navigate, Website_Easy, Website_Trust, Website_Clean, NPS_Score)

# Calculate correlations
cor_matrix <- cor(numeric_vars, use = "complete.obs")
print("Correlation Matrix:")
print(round(cor_matrix, 3))

# Correlation significance tests
cor_test_results <- cor.test(data$SUS_Score, data$NPS_Score)
print(paste("\nSUS Score vs NPS Score: r =", round(cor_test_results$estimate, 3),
            ", p =", round(cor_test_results$p.value, 4)))

#============================================================================
# 6. CREATE VISUALIZATIONS
#============================================================================

# 1. Demographics Overview
p1 <- data %>%
  count(Gender) %>%
  ggplot(aes(x = Gender, y = n, fill = Gender)) +
  geom_col() +
  geom_text(aes(label = n), vjust = -0.5) +
  labs(title = "Sample Distribution by Gender", y = "Count") +
  scale_fill_brewer(type = "qual", palette = "Set2") +
  theme(legend.position = "none")

p2 <- data %>%
  count(Tech_Affinity) %>%
  ggplot(aes(x = Tech_Affinity, y = n, fill = Tech_Affinity)) +
  geom_col() +
  geom_text(aes(label = n), vjust = -0.5) +
  labs(title = "Sample Distribution by Tech Affinity", 
       x = "Tech Affinity", y = "Count") +
  scale_fill_brewer(type = "seq", palette = "Blues") +
  theme(legend.position = "none", axis.text.x = element_text(angle = 45, hjust = 1))

# 2. SUS Score Distributions
p3 <- ggplot(data, aes(x = SUS_Score)) +
  geom_histogram(bins = 15, fill = "steelblue", alpha = 0.7, color = "white") +
  geom_vline(xintercept = mean(data$SUS_Score, na.rm = TRUE), 
             color = "red", linetype = "dashed", size = 1) +
  labs(title = "Distribution of SUS Scores", 
       x = "SUS Score", y = "Frequency") +
  annotate("text", x = mean(data$SUS_Score, na.rm = TRUE) + 5, y = Inf, 
           label = paste("Mean =", round(mean(data$SUS_Score, na.rm = TRUE), 1)), 
           vjust = 2, color = "red")

p4 <- data %>%
  count(SUS_Category) %>%
  ggplot(aes(x = SUS_Category, y = n, fill = SUS_Category)) +
  geom_col() +
  geom_text(aes(label = n), vjust = -0.5) +
  labs(title = "SUS Score Categories", 
       x = "SUS Category", y = "Count") +
  scale_fill_manual(values = c("Awful" = "#d73027", "Poor" = "#fc8d59", 
                               "OK" = "#fee08b", "Good" = "#91cf60", 
                               "Excellent" = "#4575b4")) +
  theme(legend.position = "none")

# 3. Group Comparisons - Box plots
p5 <- ggplot(data, aes(x = Gender, y = SUS_Score, fill = Gender)) +
  geom_boxplot(alpha = 0.7) +
  geom_jitter(width = 0.2, alpha = 0.5) +
  labs(title = "SUS Scores by Gender", y = "SUS Score") +
  scale_fill_brewer(type = "qual", palette = "Set2") +
  theme(legend.position = "none")

p6 <- ggplot(data, aes(x = Tech_Affinity, y = SUS_Score, fill = Tech_Affinity)) +
  geom_boxplot(alpha = 0.7) +
  geom_jitter(width = 0.2, alpha = 0.5) +
  labs(title = "SUS Scores by Tech Affinity", 
       x = "Tech Affinity", y = "SUS Score") +
  scale_fill_brewer(type = "seq", palette = "Blues") +
  theme(legend.position = "none", axis.text.x = element_text(angle = 45, hjust = 1))

# 4. Task Performance by Tech Affinity
task_data <- data %>%
  select(Tech_Affinity, Task1_Ease, Task2_Ease, Task3_Ease) %>%
  pivot_longer(cols = starts_with("Task"), names_to = "Task", values_to = "Ease_Rating") %>%
  mutate(Task = case_when(
    Task == "Task1_Ease" ~ "Task 1",
    Task == "Task2_Ease" ~ "Task 2", 
    Task == "Task3_Ease" ~ "Task 3"
  ))

p7 <- ggplot(task_data, aes(x = Tech_Affinity, y = Ease_Rating, fill = Task)) +
  geom_boxplot(alpha = 0.7) +
  facet_wrap(~Task) +
  labs(title = "Task Ease Ratings by Tech Affinity", 
       x = "Tech Affinity", y = "Ease Rating (1-5)") +
  scale_fill_brewer(type = "qual", palette = "Set1") +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))

# 5. Interest vs Performance
p8 <- ggplot(data, aes(x = Interest_Management, y = SUS_Score)) +
  geom_point(alpha = 0.6, size = 2, color = "steelblue") +
  geom_smooth(method = "lm", se = TRUE, color = "red") +
  labs(title = "SUS Score vs Interest in System Management",
       x = "Interest Level (1-4)", y = "SUS Score") +
  scale_x_continuous(breaks = 1:4, labels = c("Not Interested", "Little", "Interested", "Very Interested"))

# 6. Correlation Plot
p9 <- corrplot(cor_matrix, method = "color", type = "upper", 
               order = "hclust", tl.cex = 0.8, tl.col = "black",
               title = "Correlation Matrix of Key Variables", 
               mar = c(0,0,1,0))

# Melt the correlation matrix
library(ggplot2)
install.packages("reshape2")
library(reshape2)
cor_matrix_mat <- as.matrix(cor_matrix)
cor_melted <- data.frame(
  Var1 = rep(rownames(cor_matrix_mat), each = ncol(cor_matrix_mat)),
  Var2 = rep(colnames(cor_matrix_mat), times = nrow(cor_matrix_mat)),
  value = as.vector(cor_matrix_mat)
)
# Create the heatmap
ggplot(cor_melted, aes(Var1, Var2, fill = value)) +
  geom_tile() +
  scale_fill_gradient2(low = "red", high = "blue", mid = "white", 
                       midpoint = 0, limit = c(-1, 1), space = "Lab",
                       name = "Correlation") +
  theme_minimal() +
  theme(axis.text.x = element_text(angle = 45, vjust = 1, hjust = 1),
        axis.title.x = element_blank(),
        axis.title.y = element_blank()) +
  geom_text(aes(label = round(value, 2)), size = 2.5) +
  coord_fixed()

# 7. NPS vs SUS Relationship
p10 <- ggplot(data, aes(x = SUS_Score, y = NPS_Score)) +
  geom_point(alpha = 0.6, size = 2, color = "darkgreen") +
  geom_smooth(method = "lm", se = TRUE, color = "red") +
  labs(title = "SUS Score vs Net Promoter Score",
       x = "SUS Score", y = "NPS Score (0-10)") +
  annotate("text", x = min(data$SUS_Score, na.rm = TRUE), y = max(data$NPS_Score, na.rm = TRUE),
           label = paste("r =", round(cor(data$SUS_Score, data$NPS_Score, use = "complete.obs"), 3)),
           hjust = 0, vjust = 1, size = 4, color = "red")

# Display plots
grid.arrange(p1, p2, ncol = 2, top = "Sample Demographics")
print(p3)
print(p4)
grid.arrange(p5, p6, ncol = 2, top = "SUS Scores by Demographics")
print(p7)
print(p8)
print(p10)

#============================================================================
# 7. SUMMARY REPORT
#============================================================================

print("\n=== SUMMARY REPORT ===")
print("Key Findings:")
print("1. Sample Characteristics:")
print(paste("   - Total participants:", nrow(data)))
print(paste("   - Mean SUS Score:", round(mean(data$SUS_Score, na.rm = TRUE), 2)))
print(paste("   - SUS Score Interpretation:", 
            ifelse(mean(data$SUS_Score, na.rm = TRUE) >= 68, "Good to Excellent", 
                   ifelse(mean(data$SUS_Score, na.rm = TRUE) >= 51, "OK", "Below Average"))))

print("\n2. Statistical Tests Performed:")
print("   - Group comparisons using appropriate tests (t-test, ANOVA, Mann-Whitney, Kruskal-Wallis)")
print("   - Normality tests (Shapiro-Wilk)")
print("   - Homogeneity of variance tests (Levene's test)")
print("   - Correlation analysis")

print("\n3. Recommendations for Further Analysis:")
print("   - Consider effect sizes for significant results")
print("   - Examine qualitative feedback for insights")
print("   - Consider multiple regression analysis")
print("   - Investigate interaction effects between variables")

# Save key results to objects for further use
final_results <- list(
  sample_size = nrow(data),
  mean_sus = mean(data$SUS_Score, na.rm = TRUE),
  sd_sus = sd(data$SUS_Score, na.rm = TRUE),
  sus_categories = table(data$SUS_Category),
  demographics = list(
    gender = table(data$Gender),
    age = table(data$Age),
    education = table(data$Education),
    tech_affinity = table(data$Tech_Affinity)
  ),
  correlations = cor_matrix
)

# Flatten all results into a single data frame
results_summary <- data.frame(
  Analysis = c("Sample Size", "Mean SUS Score", "SD SUS Score",
               paste("SUS Category:", names(final_results$sus_categories)),
               paste("Gender:", names(final_results$demographics$gender)),
               paste("Age:", names(final_results$demographics$age))),
  
  Value = c(final_results$sample_size,
            final_results$mean_sus,
            final_results$sd_sus,
            as.numeric(final_results$sus_categories),
            as.numeric(final_results$demographics$gender),
            as.numeric(final_results$demographics$age))
)

write.csv(results_summary, "complete_analysis_results.csv", row.names = FALSE)

print("\nAnalysis completed! Check the plots and statistical results above.")
print("All results are saved in the 'final_results' object for further examination.")