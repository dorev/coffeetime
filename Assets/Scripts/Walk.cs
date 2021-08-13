using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Walk : MonoBehaviour
{
    private enum Direction
    {
        Left,
        Right
    }

    private Animator animator;
    private string currentState = "";
    private float currentSpeed = 0.0f;
    private Direction currentDirection = Direction.Right;
    
    public float walkSpeed = 3.0f;

    // Start is called before the first frame update
    void Start()
    {
        animator = GetComponent <Animator>();
    }

    // Update is called once per frame
    void Update()
    {
        Movement();
        currentSpeed = Input.GetAxis("Horizontal");
        animator.SetFloat("Speed", currentSpeed);

        if(currentSpeed < 0.1 && currentSpeed > -0.1)
        {
            switch(currentDirection)
            {
                case Direction.Right:
                    ChangeAnimationState("bob_idle_right");
                    break;
                case Direction.Left:
                    ChangeAnimationState("bob_idle_left");
                    break;
            }
        }
    }

    // Force transition to other animation
    void ChangeAnimationState(string newState)
    {
        if(newState == currentState)
        {
            return;
        }

        animator.Play(newState);
        currentState = newState;
    }

    void Movement()
    {
        if(Input.GetKey(KeyCode.D))
        {
            currentDirection = Direction.Right;
            ChangeAnimationState("bob_walk_right");
            transform.Translate(Vector2.right * walkSpeed * Time.deltaTime);
        }
        else if(Input.GetKey(KeyCode.A))
        {
            currentDirection = Direction.Left;
            ChangeAnimationState("bob_walk_left");
            transform.Translate(Vector2.left * walkSpeed * Time.deltaTime);
            // Rotate sprite (not useful yet but maybe...)
            //transform.eulerAngles = new Vector2(0, 0);
        }
    }
}
