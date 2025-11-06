package com.gitstats;

import java.io.IOException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.gitstats.ui.controller.MainController;

import javafx.application.Application;
import javafx.fxml.FXMLLoader;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.scene.image.Image;
import javafx.stage.Stage;

/**
 * Main JavaFX Application class for GitStats
 * 
 * This is the entry point for the JavaFX application.
 * Note: For JAR execution, use Launcher.java instead to avoid module issues.
 */
public class GitStatsApplication extends Application {
    
    private static final Logger logger = LoggerFactory.getLogger(GitStatsApplication.class);
    private static final String APP_TITLE = "GitStats - Repository Statistics Analyzer";
    private static final int DEFAULT_WIDTH = 1200;
    private static final int DEFAULT_HEIGHT = 800;
    
    private MainController mainController;
    
    @Override
    public void start(Stage primaryStage) {
        try {
            logger.info("Starting GitStats JavaFX Application");
            
            // Load FXML
            FXMLLoader loader = new FXMLLoader(
                getClass().getResource("/fxml/main.fxml")
            );
            Parent root = loader.load();
            
            // Get controller and set stage reference
            mainController = loader.getController();
            mainController.setPrimaryStage(primaryStage);
            
            // Create scene
            Scene scene = new Scene(root, DEFAULT_WIDTH, DEFAULT_HEIGHT);
            
            // Apply dark theme if available
            try {
                scene.getStylesheets().add(
                    getClass().getResource("/css/dark-theme.css").toExternalForm()
                );
                logger.info("Dark theme applied");
            } catch (Exception e) {
                logger.warn("Could not load dark theme, using default styling", e);
            }
            
            // Set up stage
            primaryStage.setTitle(APP_TITLE);
            primaryStage.setScene(scene);
            
            // Set application icon (if available)
            try {
                primaryStage.getIcons().add(
                    new Image(getClass().getResourceAsStream("/icon.png"))
                );
            } catch (Exception e) {
                logger.debug("Application icon not found, using default");
            }
            
            // Set minimum window size
            primaryStage.setMinWidth(800);
            primaryStage.setMinHeight(600);
            
            // Show the stage
            primaryStage.show();
            
            logger.info("GitStats JavaFX Application started successfully");
            
        } catch (IOException e) {
            logger.error("Failed to load FXML", e);
            showErrorAndExit("Failed to load application interface: " + e.getMessage());
        } catch (Exception e) {
            logger.error("Unexpected error during application start", e);
            showErrorAndExit("Unexpected error: " + e.getMessage());
        }
    }
    
    @Override
    public void stop() {
        logger.info("Stopping GitStats JavaFX Application");
        
        // Cleanup controller resources
        if (mainController != null) {
            mainController.cleanup();
        }
        
        logger.info("GitStats JavaFX Application stopped");
    }
    
    /**
     * Show error message and exit application
     */
    private void showErrorAndExit(String message) {
        logger.error("Fatal error: {}", message);
        javafx.scene.control.Alert alert = new javafx.scene.control.Alert(
            javafx.scene.control.Alert.AlertType.ERROR
        );
        alert.setTitle("Application Error");
        alert.setHeaderText("Failed to start GitStats");
        alert.setContentText(message);
        alert.showAndWait();
        System.exit(1);
    }
    
    /**
     * Main entry point - delegates to JavaFX Application.launch()
     * 
     * Note: When running from a JAR with JavaFX as a dependency,
     * use Launcher.main() instead to avoid module system issues.
     */
    public static void main(String[] args) {
        logger.info("GitStatsApplication.main() called");
        launch(args);
    }
}
