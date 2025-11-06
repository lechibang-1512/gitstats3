package com.gitstats;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.gitstats.ui.controller.MainController;

import javafx.application.Application;
import javafx.fxml.FXMLLoader;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.stage.Stage;

/**
 * Main JavaFX Application class for GitStats
 * 
 * This application provides comprehensive Git repository statistics
 * with an interactive JavaFX interface.
 * 
 * @author GitStats Team
 * @version 3.0.0
 */
public class GitStatsApplication extends Application {
    
    private static final Logger logger = LoggerFactory.getLogger(GitStatsApplication.class);
    private static final String APP_TITLE = "GitStats - Repository Statistics Analyzer";
    private static final int WINDOW_WIDTH = 1400;
    private static final int WINDOW_HEIGHT = 900;
    
    @Override
    public void start(Stage primaryStage) throws Exception {
        logger.info("Starting GitStats application");
        
        // Load FXML with controller
        FXMLLoader loader = new FXMLLoader(getClass().getResource("/fxml/main.fxml"));
        Parent root = loader.load();
        
        // Get controller and set stage
        MainController controller = loader.getController();
        controller.setPrimaryStage(primaryStage);
        
        // Load CSS
        Scene scene = new Scene(root, 1200, 800);
        scene.getStylesheets().add(getClass().getResource("/css/main.css").toExternalForm());
        // Optional dark theme - uncomment to enable
        // scene.getStylesheets().add(getClass().getResource("/css/dark-theme.css").toExternalForm());
        
        primaryStage.setTitle("GitStats - Repository Statistics Analyzer");
        primaryStage.setScene(scene);
        
        // Handle window close event
        primaryStage.setOnCloseRequest(event -> {
            controller.cleanup();
        });
        
        primaryStage.show();
        
        logger.info("GitStats application started successfully");
    }
    
    @Override
    public void stop() {
        logger.info("Application stopped");
    }
    
    private void showErrorAndExit(String message) {
        logger.error("Fatal error: {}", message);
        System.err.println("Error: " + message);
        System.exit(1);
    }
    
    /**
     * Main entry point
     */
    public static void main(String[] args) {
        logger.info("Launching GitStats application with args: {}", (Object) args);
        launch(args);
    }
}
