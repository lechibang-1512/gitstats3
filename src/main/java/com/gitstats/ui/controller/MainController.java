package com.gitstats.ui.controller;

import java.io.File;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.gitstats.analyzer.RepositoryAnalyzer;
import com.gitstats.model.RepositoryData;

import javafx.application.Platform;
import javafx.concurrent.Task;
import javafx.fxml.FXML;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.ProgressBar;
import javafx.scene.control.TabPane;
import javafx.scene.control.TextField;
import javafx.stage.DirectoryChooser;
import javafx.stage.Stage;

/**
 * Main window controller for GitStats JavaFX application
 */
public class MainController {
    
    private static final Logger logger = LoggerFactory.getLogger(MainController.class);
    
    @FXML private TextField repositoryPathField;
    @FXML private Button browseButton;
    @FXML private Button analyzeButton;
    @FXML private ProgressBar progressBar;
    @FXML private Label statusLabel;
    @FXML private TabPane resultsTabPane;
    
    private Stage primaryStage;
    private RepositoryData currentData;
    
    @FXML
    public void initialize() {
        logger.info("Initializing MainController");
        
        // Disable results tabs initially
        resultsTabPane.setDisable(true);
        progressBar.setVisible(false);
        
        // Setup button handlers
        browseButton.setOnAction(event -> handleBrowse());
        analyzeButton.setOnAction(event -> handleAnalyze());
    }
    
    /**
     * Handle browse button click
     */
    @FXML
    private void handleBrowse() {
        DirectoryChooser chooser = new DirectoryChooser();
        chooser.setTitle("Select Git Repository");
        
        // Set initial directory if path exists
        String currentPath = repositoryPathField.getText();
        if (currentPath != null && !currentPath.isEmpty()) {
            File currentDir = new File(currentPath);
            if (currentDir.exists() && currentDir.isDirectory()) {
                chooser.setInitialDirectory(currentDir.getParentFile());
            }
        }
        
        File selectedDir = chooser.showDialog(primaryStage);
        if (selectedDir != null) {
            repositoryPathField.setText(selectedDir.getAbsolutePath());
            logger.info("Selected repository: {}", selectedDir.getAbsolutePath());
        }
    }
    
    /**
     * Handle analyze button click
     */
    @FXML
    private void handleAnalyze() {
        String repoPath = repositoryPathField.getText();
        
        if (repoPath == null || repoPath.trim().isEmpty()) {
            showError("Please select a repository path");
            return;
        }
        
        File repoDir = new File(repoPath);
        if (!repoDir.exists() || !repoDir.isDirectory()) {
            showError("Invalid repository path");
            return;
        }
        
        // Check if it's a git repository
        File gitDir = new File(repoDir, ".git");
        if (!gitDir.exists()) {
            showError("Selected directory is not a Git repository");
            return;
        }
        
        // Start analysis in background
        startAnalysis(repoDir);
    }
    
    /**
     * Start repository analysis in background thread
     */
    private void startAnalysis(File repoDir) {
        logger.info("Starting analysis of: {}", repoDir);
        
        // Disable UI during analysis
        analyzeButton.setDisable(true);
        browseButton.setDisable(true);
        progressBar.setVisible(true);
        progressBar.setProgress(0);
        statusLabel.setText("Initializing analysis...");
        
        Task<RepositoryData> analysisTask = new Task<>() {
            @Override
            protected RepositoryData call() throws Exception {
                RepositoryAnalyzer analyzer = new RepositoryAnalyzer(repoDir);
                
                return analyzer.analyze((progress, message) -> {
                    Platform.runLater(() -> {
                        progressBar.setProgress(progress);
                        statusLabel.setText(message);
                    });
                });
            }
        };
        
        analysisTask.setOnSucceeded(event -> {
            currentData = analysisTask.getValue();
            displayResults(currentData);
            
            analyzeButton.setDisable(false);
            browseButton.setDisable(false);
            progressBar.setVisible(false);
            statusLabel.setText("Analysis complete!");
            
            logger.info("Analysis completed successfully");
        });
        
        analysisTask.setOnFailed(event -> {
            Throwable exception = analysisTask.getException();
            logger.error("Analysis failed", exception);
            
            showError("Analysis failed: " + exception.getMessage());
            
            analyzeButton.setDisable(false);
            browseButton.setDisable(false);
            progressBar.setVisible(false);
            statusLabel.setText("Analysis failed");
        });
        
        // Run in background thread
        Thread analysisThread = new Thread(analysisTask);
        analysisThread.setDaemon(true);
        analysisThread.start();
    }
    
    /**
     * Display analysis results
     */
    private void displayResults(RepositoryData data) {
        logger.info("Displaying results for: {}", data.getProjectName());
        
        // Enable results tabs
        resultsTabPane.setDisable(false);
  
        showInfo("Analysis Results", 
            String.format("""
                Analysis complete for %s
                
                Total Commits: %d
                Total Files: %d
                Total Lines: %d
                Authors: %d
                Age: %d days""",
                data.getProjectName(),
                data.getTotalCommits(),
                data.getTotalFiles(),
                data.getTotalLines(),
                data.getTotalAuthors(),
                data.getAgeDays()));
    }
    
    /**
     * Handle settings menu item
     */
    @FXML
    public void handleSettings() {
        logger.info("Settings menu clicked");
    }
    
    /**
     * Handle export menu item
     */
    @FXML
    public void handleExport() {
        if (currentData == null) {
            showWarning("No data to export. Please analyze a repository first.");
            return;
        }
        
        logger.info("Export menu clicked");
    }
    
    /**
     * Handle about menu item
     */
    @FXML
    public void handleAbout() {
        showInfo("About GitStats", 
            """
            GitStats JavaFX v3.0.0
            
            A comprehensive Git repository statistics analyzer
            with modern JavaFX interface.
            
            Features:
            • Repository analysis
            • Code quality metrics
            • Team collaboration insights
            • Interactive visualizations""");
    }
    
    /**
     * Cleanup resources
     */
    public void cleanup() {
        logger.info("Cleaning up resources");
    }
    
    // Utility methods
    
    private void showError(String message) {
        Alert alert = new Alert(Alert.AlertType.ERROR);
        alert.setTitle("Error");
        alert.setHeaderText(null);
        alert.setContentText(message);
        alert.showAndWait();
    }
    
    private void showWarning(String message) {
        Alert alert = new Alert(Alert.AlertType.WARNING);
        alert.setTitle("Warning");
        alert.setHeaderText(null);
        alert.setContentText(message);
        alert.showAndWait();
    }
    
    private void showInfo(String title, String message) {
        Alert alert = new Alert(Alert.AlertType.INFORMATION);
        alert.setTitle(title);
        alert.setHeaderText(null);
        alert.setContentText(message);
        alert.showAndWait();
    }
    
    public void setPrimaryStage(Stage stage) {
        this.primaryStage = stage;
    }
}
