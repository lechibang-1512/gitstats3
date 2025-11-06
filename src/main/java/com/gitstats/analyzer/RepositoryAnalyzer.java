package com.gitstats.analyzer;

import java.io.File;
import java.io.IOException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.gitstats.core.Configuration;
import com.gitstats.core.GitCommandExecutor;
import com.gitstats.model.AuthorStatistics;
import com.gitstats.model.CodeMetrics;
import com.gitstats.model.ProjectHealthMetrics;
import com.gitstats.model.RepositoryData;

/**
 * Main repository analyzer that orchestrates all analysis components
 * 
 * This class coordinates the analysis of:
 * - Commit history
 * - File statistics
 * - Author contributions
 * - Branch information
 * - Code quality metrics
 */
public class RepositoryAnalyzer {
    
    private static final Logger logger = LoggerFactory.getLogger(RepositoryAnalyzer.class);
    
    private final GitCommandExecutor gitExecutor;
    private final ExecutorService executorService;
    
    // Sub-analyzers
    private final CommitAnalyzer commitAnalyzer;
    private final FileAnalyzer fileAnalyzer;
    private final BranchAnalyzer branchAnalyzer;
    
    public RepositoryAnalyzer(File repositoryPath) {
        Configuration config = Configuration.getInstance();
        this.gitExecutor = new GitCommandExecutor(repositoryPath);
        this.executorService = Executors.newFixedThreadPool(config.getProcesses());
        
        // Initialize sub-analyzers
        this.commitAnalyzer = new CommitAnalyzer(gitExecutor, executorService);
        this.fileAnalyzer = new FileAnalyzer(gitExecutor, config);
        this.branchAnalyzer = new BranchAnalyzer(gitExecutor);
    }
    
    /**
     * Perform complete repository analysis
     * 
     * @param progressCallback Callback for progress updates
     * @return RepositoryData containing all statistics
     * @throws IOException if analysis fails
     * @throws InterruptedException if analysis is interrupted
     */
    public RepositoryData analyze(ProgressCallback progressCallback) throws IOException, InterruptedException {
        logger.info("Starting repository analysis: {}", gitExecutor.getRepositoryPath());
        
        // Validate repository
        if (!gitExecutor.isValidRepository()) {
            throw new IOException("Not a valid Git repository: " + gitExecutor.getRepositoryPath());
        }
        
        // Initialize data container
        String projectName = gitExecutor.getRepositoryPath().getName();
        RepositoryData data = new RepositoryData(projectName, 
            gitExecutor.getRepositoryPath().getAbsolutePath());
        
        try {
            // Phase 1: Analyze commits (40% of work)
            updateProgress(progressCallback, 0.0, "Analyzing commit history...");
            commitAnalyzer.analyze(data, (percent, message) -> 
                updateProgress(progressCallback, percent * 0.4, "Analyzing commits...")
            );
            
            // Phase 2: Analyze files (30% of work)
            updateProgress(progressCallback, 0.4, "Analyzing files...");
            fileAnalyzer.analyze(data, (percent, message) -> 
                updateProgress(progressCallback, 0.4 + percent * 0.3, "Analyzing files...")
            );
            
            // Phase 3: Analyze branches (10% of work)
            updateProgress(progressCallback, 0.7, "Analyzing branches...");
            branchAnalyzer.analyze(data, (percent, message) -> 
                updateProgress(progressCallback, 0.7 + percent * 0.1, "Analyzing branches...")
            );
            
            // Phase 4: Calculate aggregate metrics (10% of work)
            updateProgress(progressCallback, 0.8, "Calculating metrics...");
            calculateAggregateMetrics(data);
            
            // Phase 5: Calculate health metrics (10% of work)
            updateProgress(progressCallback, 0.9, "Calculating health metrics...");
            calculateHealthMetrics(data);
            
            updateProgress(progressCallback, 1.0, "Analysis complete!");
            
            logger.info("Repository analysis completed successfully");
            return data;
            
        } finally {
            shutdown();
        }
    }
    
    /**
     * Calculate aggregate metrics from collected data
     */
    private void calculateAggregateMetrics(RepositoryData data) {
        // Calculate total lines from all files
        long totalSource = 0;
        long totalComment = 0;
        long totalBlank = 0;
        
        for (CodeMetrics metrics : data.getFileMetrics().values()) {
            totalSource += metrics.getLocProgram();
            totalComment += metrics.getLocComment();
            totalBlank += metrics.getLocBlank();
        }
        
        data.setTotalSourceLines(totalSource);
        data.setTotalCommentLines(totalComment);
        data.setTotalBlankLines(totalBlank);
        data.setTotalLines(totalSource + totalComment + totalBlank);
        
        logger.debug("Calculated aggregate metrics: {} total lines", data.getTotalLines());
    }
    
    /**
     * Calculate project health metrics
     */
    private void calculateHealthMetrics(RepositoryData data) {
        ProjectHealthMetrics health = new ProjectHealthMetrics();
        
        // Calculate bus factor
        health.setBusFactor(calculateBusFactor(data));
        
        // Calculate average complexity
        if (!data.getFileMetrics().isEmpty()) {
            double totalComplexity = data.getFileMetrics().values().stream()
                .mapToInt(CodeMetrics::getCyclomaticComplexity)
                .sum();
            health.setAverageComplexity(totalComplexity / data.getFileMetrics().size());
        }
        
        // Calculate average maintainability index
        if (!data.getFileMetrics().isEmpty()) {
            double totalMI = data.getFileMetrics().values().stream()
                .mapToDouble(CodeMetrics::getMaintainabilityIndex)
                .sum();
            health.setAverageMaintainabilityIndex(totalMI / data.getFileMetrics().size());
        }
        
        // Count files by MI category
        for (CodeMetrics metrics : data.getFileMetrics().values()) {
            double mi = metrics.getMaintainabilityIndexRaw();
            if (mi >= 85) {
                health.setGoodFiles(health.getGoodFiles() + 1);
            } else if (mi >= 65) {
                health.setModerateFiles(health.getModerateFiles() + 1);
            } else if (mi >= 0) {
                health.setDifficultFiles(health.getDifficultFiles() + 1);
            } else {
                health.setCriticalFiles(health.getCriticalFiles() + 1);
            }
        }
        
        // Count large and complex files
        int largeFiles = 0;
        int complexFiles = 0;
        for (CodeMetrics metrics : data.getFileMetrics().values()) {
            if (metrics.getLocPhysical() > 500) {
                largeFiles++;
            }
            if (metrics.getCyclomaticComplexity() > 20) {
                complexFiles++;
            }
        }
        health.setLargeFilesCount(largeFiles);
        health.setComplexFilesCount(complexFiles);
        
        // Calculate code quality score (0-100)
        double qualityScore = calculateCodeQualityScore(health, data);
        health.setCodeQualityScore(qualityScore);
        
        // Generate recommendations
        generateRecommendations(health);
        
        data.setHealthMetrics(health);
        logger.debug("Calculated health metrics with quality score: {}", qualityScore);
    }
    
    /**
     * Calculate bus factor (minimum contributors for 50% of commits)
     */
    private int calculateBusFactor(RepositoryData data) {
        if (data.getAuthorStats().isEmpty()) {
            return 0;
        }
        
        int totalCommits = data.getTotalCommits();
        int targetCommits = totalCommits / 2;
        int cumulativeCommits = 0;
        int busFactor = 0;
        
        // Sort authors by commit count
        java.util.List<AuthorStatistics> sortedAuthors = data.getAuthorStats().values().stream()
            .sorted((a, b) -> Integer.compare(b.getTotalCommits(), a.getTotalCommits()))
            .toList();
        
        for (AuthorStatistics author : sortedAuthors) {
            cumulativeCommits += author.getTotalCommits();
            busFactor++;
            if (cumulativeCommits >= targetCommits) {
                break;
            }
        }
        
        return busFactor;
    }
    
    /**
     * Calculate overall code quality score (0-100)
     */
    private double calculateCodeQualityScore(ProjectHealthMetrics health, RepositoryData data) {
        double score = 100.0;
        
        // Penalty for high average complexity (max -30 points)
        if (health.getAverageComplexity() > 10) {
            score -= Math.min(30, (health.getAverageComplexity() - 10) * 3);
        }
        
        // Penalty for low maintainability (max -30 points)
        if (health.getAverageMaintainabilityIndex() < 65) {
            score -= Math.min(30, (65 - health.getAverageMaintainabilityIndex()) * 0.5);
        }
        
        // Penalty for large files (max -20 points)
        if (data.getTotalFiles() > 0) {
            double largeFileRatio = (double) health.getLargeFilesCount() / data.getTotalFiles();
            score -= Math.min(20, largeFileRatio * 100);
        }
        
        // Penalty for low bus factor (max -20 points)
        if (health.getBusFactor() <= 2) {
            score -= 20;
        } else if (health.getBusFactor() <= 4) {
            score -= 10;
        }
        
        return Math.max(0, score);
    }
    
    /**
     * Generate health recommendations
     */
    private void generateRecommendations(ProjectHealthMetrics health) {
        if (health.getCodeQualityScore() < 50) {
            health.addRecommendation("⚠️ Code quality score is low. Consider significant refactoring.");
        }
        
        if (health.getBusFactor() <= 2) {
            health.addRecommendation("🔴 Bus factor is very low. Knowledge is concentrated in few contributors.");
        }
        
        if (health.getComplexFilesCount() > 0) {
            health.addRecommendation("📊 " + health.getComplexFilesCount() + 
                " files have high cyclomatic complexity. Consider simplifying.");
        }
        
        if (health.getCriticalFiles() > 0) {
            health.addRecommendation("⛔ " + health.getCriticalFiles() + 
                " files have critical maintainability issues. Immediate attention needed.");
        }
    }
    
    private void updateProgress(ProgressCallback callback, double progress, String message) {
        if (callback != null) {
            callback.onProgress(progress, message);
        }
    }
    
    /**
     * Shutdown executor service
     */
    public void shutdown() {
        executorService.shutdown();
        try {
            if (!executorService.awaitTermination(10, TimeUnit.SECONDS)) {
                executorService.shutdownNow();
            }
        } catch (InterruptedException e) {
            executorService.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }
    
    /**
     * Progress callback interface
     */
    @FunctionalInterface
    public interface ProgressCallback {
        void onProgress(double progress, String message);
    }
}
